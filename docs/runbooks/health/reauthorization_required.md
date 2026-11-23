# REAUTHORIZATION_REQUIRED

**Owner:** CUSTOMER · **Status:** UNHEALTHY

Refreshing the connection's token was rejected on 4 separate days, so automatic refresh has
stopped (AUTH-06). Someone with access at the vendor must authorise again: create a connect
session with `connection_id` set (`POST /v1/connect_sessions`) and open its `url`. The
connection keeps its data and history; syncs resume after the new authorisation verifies.
