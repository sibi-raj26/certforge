# CertForge v2.3 – Excel -> PDF Internship Certificates

## Run (Windows)
1. Unzip this folder somewhere NEW (do not copy over an old version).
2. Double-click `run.bat`  (or in terminal:  py -m pip install -r requirements.txt  then  py app.py)
3. Open http://127.0.0.1:5000 and press Ctrl+F5. The header must show "v2.3".
4. Upload `candidates_upload_ready.xlsx`.

Stop any old server first (Ctrl+C in its terminal).

## Optional
- AI citations: set ANTHROPIC_API_KEY (PowerShell:  $env:ANTHROPIC_API_KEY="sk-ant-..." ).
- Branding: in "Certificate settings" upload company logo, seal, and two signature images (PNG/JPG, transparent PNG is best). Without uploads the app draws a monogram logo, gold seal and handwriting-font signatures.
- Company name and signatories are edited in the "Certificate settings" panel.

Excel columns: Name, Role, Dept, Year of Study, Start Date, End Date, Score (required), Email, Attendance, Company Rating.
