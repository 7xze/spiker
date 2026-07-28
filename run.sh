#!/bin/bash
# Z3R0 سكريبت تشغيل سريع مع SSL اختياري

HOST="0.0.0.0"
PORT=443
CERT="cert.pem"
KEY="key.pem"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[*] شهادة SSL غير موجودة، جاري توليد شهادة ذاتية..."
    ./tools/gen_cert.sh
fi

echo "[*] تشغيل Z3R0 Ghost Proxy على المنفذ $PORT..."
python3 z3r0_ghost_proxy.py --host $HOST --port $PORT --ssl-cert $CERT --ssl-key $KEY --config config.json