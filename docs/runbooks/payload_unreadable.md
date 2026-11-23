# payload_unreadable

**Severity:** ticket · **Subject:** `key version <n>` · **Raised by:** `maintenance.payload_reencrypt`

## What it means

The re-encryption job (STORE-09) found stored vendor payloads it cannot open with any key
in `PAYLOAD_KEYS`: they were sealed with a key version that is no longer loaded, or with a
different key under the same version number. Canonical records are unaffected (payloads are
the raw vendor JSON kept beside them), but those payloads can no longer be read.

## Diagnose

1. `detail.loaded_versions` lists the versions this worker holds. Compare with the key
   history: was a version dropped before the job finished re-sealing (`remaining` > 0)?
2. Count by version:
   ```sql
   select get_byte(vendor_data, 1) as key_version, count(*) from data.vulnerability_finding
    where get_byte(vendor_data, 0) = 2 group by 1;
   ```

## Fix

- A version was dropped too early: put it back in `PAYLOAD_KEYS`, let the job finish
  (`remaining` reaches 0), then drop it again.
- The key is truly lost: the payloads are unrecoverable. The next full sync of each
  affected connection rewrites them from the vendor; trigger one with the operator
  `trigger` repair (`{"full": true}`) to do it now.
