# Verify a SecureFabric webhook (Ruby, standard library only).
require "openssl"

# Constant-time comparison (works on every Ruby; newer ones also have
# OpenSSL.fixed_length_secure_compare).
def secure_compare(a, b)
  return false unless a.bytesize == b.bytesize

  diff = 0
  a.bytes.zip(b.bytes) { |x, y| diff |= x ^ y }
  diff.zero?
end

def verify(secret, signature_header, timestamp, raw_body, tolerance_seconds = 300)
  ts = begin
    Integer(timestamp)
  rescue ArgumentError, TypeError
    return false
  end
  return false if (Time.now.to_i - ts).abs > tolerance_seconds # replay protection

  expected = "v1=" + OpenSSL::HMAC.hexdigest("SHA256", secret, "#{ts}." + raw_body)
  # During a secret rotation two signatures are sent, comma-separated.
  signature_header.split(",").any? { |part| secure_compare(part.strip, expected) }
end

if __FILE__ == $PROGRAM_NAME
  # ruby verify.rb <secret> <SecureFabric-Signature> <SecureFabric-Timestamp> < body
  body = $stdin.binmode.read
  exit(verify(ARGV[0], ARGV[1], ARGV[2], body) ? 0 : 1)
end
