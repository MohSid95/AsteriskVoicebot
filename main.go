package main

import (
	"context"
	"log"
)

func main() {

	cfg := loadConfig()

	ctx := context.Background()

	log.Printf("listening for AudioSocket connections on %s -> WS %s", cfg.listenAddr, cfg.wsURL)
	if err := Listen(ctx, cfg); err != nil {
		log.Fatal("listen failure:", err)
	}
	log.Println("exiting")
}
