// Verify a SecureFabric webhook (Go, standard library only).
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"math"
	"os"
	"strconv"
	"strings"
	"time"
)

// Verify reports whether any v1= signature matches and the timestamp is fresh.
func Verify(secret, signatureHeader, timestamp string, rawBody []byte, tolerance time.Duration) bool {
	ts, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return false
	}
	if math.Abs(float64(time.Now().Unix()-ts)) > tolerance.Seconds() { // replay protection
		return false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(strconv.FormatInt(ts, 10) + "."))
	mac.Write(rawBody)
	expected := "v1=" + hex.EncodeToString(mac.Sum(nil))
	// During a secret rotation two signatures are sent, comma-separated.
	for _, part := range strings.Split(signatureHeader, ",") {
		if hmac.Equal([]byte(strings.TrimSpace(part)), []byte(expected)) {
			return true
		}
	}
	return false
}

// go run verify.go <secret> <SecureFabric-Signature> <SecureFabric-Timestamp> < body
func main() {
	body, _ := io.ReadAll(os.Stdin)
	if Verify(os.Args[1], os.Args[2], os.Args[3], body, 5*time.Minute) {
		os.Exit(0)
	}
	os.Exit(1)
}
