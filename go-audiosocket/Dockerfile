FROM golang:1.23-alpine AS builder

WORKDIR /app

# Copy go mod and source files
COPY go.mod ./
COPY *.go ./
RUN go mod tidy && go mod download

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o voicebot .

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates
WORKDIR /root/

# Copy the binary from builder stage
COPY --from=builder /app/voicebot .

# Expose the port
EXPOSE 9092

# Run the application
CMD ["./voicebot"]