package main

import (
	"context"
	"fmt"
	"log"
	"net"
)

// Listen listens for and responds to AudioSocket connections
func Listen(ctx context.Context, cfg Config) error {
	l, err := net.Listen("tcp", cfg.listenAddr)
	if err != nil {
		return fmt.Errorf("failed to bind listener to socket %s: %w", cfg.listenAddr, err)
	}

	go func() {
		<-ctx.Done()
		_ = l.Close()
	}()

	for {
		conn, err := l.Accept()
		if err != nil {
			select {
			case <-ctx.Done():
				return nil
			default:
				log.Printf("failed to accept new connection: %v", err)
				continue
			}
		}
		go handleCall(ctx, conn, cfg)
	}
}
