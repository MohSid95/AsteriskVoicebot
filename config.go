package main

import (
	"os"
	"time"

	"github.com/CyCoreSystems/audiosocket"
)

type Config struct {
	listenAddr      string
	wsURL           string
	maxCallDuration time.Duration // maxCallDuration is the maximum amount of time to allow a call to be up before it is terminated.
	slinChunkSize   int           // slinChunkSize is the number of bytes which should be sent per Slin audiosocket message.
	wsWriteTimeout  time.Duration // write deadline per WS message
}

func getEnv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func loadConfig() Config {
	return Config{
		listenAddr: getEnv("LISTEN_ADDR",
			":9092"),
		wsURL: getEnv("WS_URL",
			"ws://localhost:8080/media"),
		maxCallDuration: 2 * time.Minute,
		slinChunkSize:   int(audiosocket.DefaultSlinChunkSize), //  320 bytes (20ms @ 8kHz, 16-bit signed linear)
		wsWriteTimeout:  250 * time.Millisecond,
	}
}
