#!/bin/sh
set -u

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

run_quotes() {
  name="$1"
  shift

  while true; do
    log "starting quotes group: $name -> $*"
    kase-pilot stream-quotes "$@" --save --reconnect
    code=$?
    log "quotes group $name exited with code $code; restarting in 5s"
    sleep 5
  done
}

run_orderbook() {
  ticker="$1"

  while true; do
    log "starting orderbook: $ticker"
    kase-pilot stream-orderbook "$ticker" --save --reconnect
    code=$?
    log "orderbook $ticker exited with code $code; restarting in 5s"
    sleep 5
  done
}

run_quotes core \
  HSBK.KZ ASBN.KZ CCBN.KZ KSPI.KZ &

run_quotes group2 \
  KEGC.KZ AIRA.KZ KZTO.KZ KMGZ.KZ GB_ALTN.KZ &

for ticker in \
  HSBK.KZ \
  ASBN.KZ \
  CCBN.KZ \
  KSPI.KZ \
  KEGC.KZ \
  AIRA.KZ \
  KZTO.KZ \
  KMGZ.KZ \
  GB_ALTN.KZ
do
  run_orderbook "$ticker" &
done

log "all collectors started"
wait