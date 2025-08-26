// WIP

package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"sync/atomic"
	"time"

	"github.com/CyCoreSystems/audiosocket"
	"github.com/gorilla/websocket"
)

func handleCall(pCtx context.Context, c net.Conn, cfg Config) {
	callCtx, cancel := context.WithTimeout(pCtx, cfg.maxCallDuration)
	defer func() {
		cancel()
		_, _ = c.Write(audiosocket.HangupMessage())
		_ = c.Close()
	}()

	id, err := audiosocket.GetID(c)
	if err != nil {
		log.Println("GetID:", err)
		return
	}
	log.Printf("call %s connected", id)

	// REMOVE FOR PRODUCTION: Audio flow counters
	var bytesToWS int64   // bytes sent to WebSocket (from Asterisk)
	var bytesToAS int64   // bytes sent to AudioSocket (to Asterisk)

	// REMOVE FOR PRODUCTION: Start periodic logging
	logTicker := time.NewTicker(5 * time.Second)
	defer logTicker.Stop()
	go func() {
		for {
			select {
			case <-callCtx.Done():
				return
			case <-logTicker.C:
				toWS := atomic.SwapInt64(&bytesToWS, 0)
				toAS := atomic.SwapInt64(&bytesToAS, 0)
				log.Printf("=== AUDIO FLOW DEBUG (call %s) ===", id)
				log.Printf("Audio bytes sent TO WebSocket (last 5s): %d", toWS)
				log.Printf("Audio bytes sent TO Asterisk (last 5s): %d", toAS)
				log.Printf("===========================================")
			}
		}
	}()

	// Connect to Python WebSocket
	ws, resp, err := websocket.DefaultDialer.Dial(cfg.wsURL, nil)
	if err != nil {
		if resp != nil {
			b, _ := io.ReadAll(resp.Body)
			log.Printf("WS handshake failed: status=%d %s\n%s", resp.StatusCode, resp.Status, string(b))
		}
		log.Fatalf("WS dial: %v", err)
	}
	if err != nil {
		println(cfg.wsURL)
		log.Printf("WS dial error: %v", err)
		return
	}
	defer ws.Close()
	// Cancel both directions if the context ends
	go func() {
		<-callCtx.Done()
		_ = ws.Close() // triggers the WS read loop to exit
		_ = c.Close()  // triggers the AudioSocket read loop to exit
	}()

	errc := make(chan error, 2)

	// AudioSocket → WebSocket
	go func() {
		for {
			// optional fast-exit:
			select {
			case <-callCtx.Done():
				errc <- callCtx.Err()
				return
			default:
			}

			m, err := audiosocket.NextMessage(c)
			if err != nil {
				errc <- err
				return
			}

			switch m.Kind() {
			case audiosocket.KindHangup:
				errc <- io.EOF
				return
			case audiosocket.KindSlin:
				payload := m.Payload()
				if len(payload) != cfg.slinChunkSize {
					continue
				}
				_ = ws.SetWriteDeadline(time.Now().Add(cfg.wsWriteTimeout))
				if err := ws.WriteMessage(websocket.BinaryMessage, payload); err != nil {
					errc <- fmt.Errorf("write WS: %w", err)
					return
				}
				atomic.AddInt64(&bytesToWS, int64(len(payload))) // REMOVE FOR PRODUCTION
			}
		}
	}()

	// WebSocket → AudioSocket
	go func() {
		for {
			select {
			case <-callCtx.Done():
				errc <- callCtx.Err()
				return
			default:
			}

			mt, msg, err := ws.ReadMessage()
			if err != nil {
				errc <- fmt.Errorf("read WS: %w", err)
				return
			}
			if mt != websocket.BinaryMessage || len(msg) != cfg.slinChunkSize {
				continue
			}
			if _, err := c.Write(audiosocket.SlinMessage(msg)); err != nil {
				errc <- fmt.Errorf("write AS: %w", err)
				return
			}
			atomic.AddInt64(&bytesToAS, int64(len(msg))) // REMOVE FOR PRODUCTION
		}
	}()

	if err := <-errc; err != nil && !errors.Is(err, io.EOF) {
		log.Printf("call %s ended with error: %v", id, err)
	} else {
		log.Printf("call %s ended", id)
	}
}
