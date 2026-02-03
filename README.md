# paperless-ngx ASN Label Generator (GUI) – Avery L4731 / L4731REV

GUI-Tool (Tkinter), das ASN-Labels als PDF erzeugt – QR oder Code128 – inkl. Kalibrierung (Offset & Pitch-Drift) für saubere Ausdrucke auf echten Etikettenbögen.

> Hinweis: Inoffizielles Tool, nicht affiliated mit paperless-ngx.

---

## Voraussetzungen

- **Python 3.10+**
- **Git** (nur nötig, wenn du direkt von GitHub installieren willst)
- Auf **Linux** ggf. zusätzlich: **Tkinter** (siehe unten)

---

## Installation & Start

### Windows (empfohlen)

#### 1) Python installieren
- Lade Python von der offiziellen Seite.
- **Wichtig:** Beim Installer unbedingt **„Add Python to PATH“** aktivieren.

Prüfen:
```bash
python --version
pip --version
```

#### 2) Installation direkt von GitHub
```bash
pip install git+https://github.com/DEINNAME/paperless-asn-label-generator
paperless-asn-labels
```

> Wenn `pip` meldet, dass `git` fehlt: Git für Windows installieren, dann nochmal versuchen.

---

### macOS

#### 1) Python prüfen/ installieren
Prüfen:
```bash
python3 --version
pip3 --version
```

Falls Python fehlt oder zu alt ist, am einfachsten über Homebrew:
```bash
brew install python
```

#### 2) Installation direkt von GitHub
```bash
pip3 install git+https://github.com/DEINNAME/paperless-asn-label-generator
paperless-asn-labels
```

> Falls `paperless-asn-labels` nicht gefunden wird, starte einmal neu das Terminal oder nutze:
```bash
python3 -m paperless_asn_label_generator
```

---

### Linux

#### 1) Python + pip prüfen
```bash
python3 --version
pip3 --version
```

Falls nötig (Debian/Ubuntu):
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

#### 2) Tkinter installieren (wichtig für GUI)
Debian/Ubuntu:
```bash
sudo apt-get install -y python3-tk
```

Fedora:
```bash
sudo dnf install -y python3-tkinter
```

Arch:
```bash
sudo pacman -S tk
```

#### 3) Installation direkt von GitHub
```bash
pip3 install git+https://github.com/DEINNAME/paperless-asn-label-generator
paperless-asn-labels
```

---

## Nutzung

- Start-Nummer wählen (z.B. 1 oder 190)
- Prefix setzen (muss zu paperless-ngx passen)
- Führende Nullen einstellen (z.B. 7 → `ASN0000001`)
- Menge als **Labels** oder **A4-Blätter**
- Code-Typ: **QR** oder **CODE128**
- Optional: Rahmen aktivieren (hilft beim Kalibrieren)
- „PDF erzeugen…“ → Datei speichern

---

## Prefix in paperless-ngx

Der Prefix muss zu deiner paperless-ngx Einstellung passen:

- `PAPERLESS_CONSUMER_ASN_BARCODE_PREFIX`

Beispiel: Wenn du in paperless-ngx `ASN` nutzt, dann hier auch `ASN`.

---

## Druck-Hinweis (sehr wichtig)

Bitte im PDF-Viewer/Printer **100%** drucken:
- **kein** „An Seite anpassen“
- **kein** „Skalieren“
- **kein** „Fit to Page“

Wenn die Position nicht exakt passt:
- Rahmen aktivieren
- Offset X/Y und Pitch-Δ anpassen

---

## Entwicklung (Repo klonen & lokal starten)

```bash
git clone https://github.com/DEINNAME/paperless-asn-label-generator
cd paperless-asn-label-generator

# Virtuelle Umgebung
python -m venv .venv
# Windows:
# .venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -e .
paperless-asn-labels
```

---

## Lizenz
GNU AGPLv3 (siehe LICENSE)
