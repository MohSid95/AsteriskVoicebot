package main

import (
	"fmt"
	"log"
	"net"

	"github.com/CyCoreSystems/audiosocket"
)

func main() {
	listener, err := net.Listen("tcp", ":9092")
	if err != nil {
		log.Fatal("Failed to listen on port 9092:", err)
	}
	defer listener.Close()

	fmt.Println("AudioSocket server listening on :9092")

	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Println("Failed to accept connection:", err)
			continue
		}

		fmt.Printf("New connection from %s\n", conn.RemoteAddr())
		go handleConnection(conn)
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()
	
	for {
		msg, err := audiosocket.NextMessage(conn)
		if err != nil {
			fmt.Printf("Error reading message: %v\n", err)
			break
		}

		switch msg.Kind() {
		case audiosocket.KindHangup:
			fmt.Println("Received hangup message")
			return
		case audiosocket.KindID:
			fmt.Printf("Connection ID: %s\n", string(msg.Payload()))
		case audiosocket.KindSlin:
			payload := msg.Payload()
			fmt.Printf("Audio data received: %d bytes - %v\n", len(payload), payload[:min(16, len(payload))])
		case audiosocket.KindDTMF:
			fmt.Printf("DTMF received: %s\n", string(msg.Payload()))
		default:
			fmt.Printf("Unknown message type: %d\n", msg.Kind())
		}
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}