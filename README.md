# Bauer Hackathon | Audiostack guide

## Recipe for generating dynamic ads

`create_dynamic_ad.py` contains an example of creating a dynamic ad for Coinspot. The ad is created with multiple dynamic parameters:
- BTC price from coingecko API
- location
- time of day at specified location

It's using Audioform, which is a data structure used in Audiostack's API to define audio production end to end.

We hope it'll serve as a good foundation for understanding how to use Audioforms for dynamic creatives that will enable participants to easily build their own ads by implementing their own subclass for `AudioformAdBuilder`. 

## Setup

1. Create a virtual environment `python3 -m venv .venv`
2. Activate it `source .venv/bin/activate`
3. Install requirements `pip install -r requirements.txt`
4. Set this API key as env var: `export AUDIOSTACK_API_KEY=<key>`
5. Run the script `python create_dynamic_ad.py`

## Docs

https://docs.audiostack.ai

## AudioStack API common use-cases

**Base URL:** `https://v2.api.audio`  
**Auth:** `x-api-key` header on every request

```python
import requests, time

BASE = "https://v2.api.audio"
HEADERS = {
    "x-api-key": "YOUR_API_KEY",
    "x-assume-org": "YOUR_ORG_ID",   # optional, used to target a specific organization the key has access to
}
```

### Quick Reference

| Task | Endpoint | Method |
|------|----------|--------|
| Get upload URL + fileId | `/files` | POST |
| Upload file bytes | `uploadUrl` from above | PUT |
| Set file category | `/files/{fileId}` | PATCH |
| List file types | `/files/file-categories` | GET |
| Query voices | `/assets/voices/query` | POST |
| Query sound templates | `/assets/sound-templates/query` | POST |
| Generate ad (AI) | `/creator/brief` | POST |
| Build audioform | `/audioforms/` | POST |
| Get audioform result | `/audioforms/{id}` | GET |
| Create story/bulletin | `/creator/story` | POST |
| Get story result | `/creator/story?storyId=` | GET |
| Submit batch | `/audioforms/batches` | POST |
| Get batch result | `/audioforms/batches/{id}` | GET |

### Defaults you can rely on

- `encoderPreset` default: `mp3`
- `mixingPreset` default: `balanced`
- `voicePreset` default: `standard` → **always override with `expressive`**
- `smartFit` default: `false` → **always set `true` when using music**
- Batch max: 1000 items

### Response codes

- `200` — complete
- `202` — still processing (poll again)
- `422` — validation error (check request body)

---

### 1. Upload a File and Set Its Type

Upload your own audio assets (voice recordings, music beds, sound effects) so they can be referenced in audioforms. The API uses a two-step pre-signed URL pattern: register the file first, then PUT the bytes directly to storage.

**Valid `category_name` values:** `voice`, `music`, `sound effect`, `media` (default)

```python
import os

def upload_file(local_path: str, category_name: str = "media") -> str:
    """Returns the fileId of the uploaded file."""
    file_name = os.path.basename(local_path)

    # Step 1: request an upload URL
    resp = requests.post(
        f"{BASE}/files",
        headers=HEADERS,
        json={"fileName": file_name}
    )
    resp.raise_for_status()
    payload = resp.json()
    upload_url = payload["uploadUrl"]
    file_id = payload["fileId"]

    # Step 2: upload the file bytes
    with open(local_path, "rb") as f:
        put_resp = requests.put(upload_url, data=f)
    put_resp.raise_for_status()

    # Step 3: set the category (file type)
    patch_resp = requests.patch(
        f"{BASE}/files/{file_id}",
        headers=HEADERS,
        json={"categoryName": category_name}
    )
    patch_resp.raise_for_status()
    print(f"Uploaded {file_name} → fileId: {file_id}")
    return file_id
```

**List available file types** to find the right `categoryName`:

```python
resp = requests.get(f"{BASE}/files/file-categories", headers=HEADERS)
for ft in resp.json()["fileTypes"]:
    print(ft["name"], "→ categories:", [c["name"] for c in ft["fileCategories"]])
```

---

### 2. Query the Voice Library

Browse AudioStack's voice library to find the right voice for your project. Use filters to narrow by provider, accent, gender, or language — the `alias` in the result is what you pass into audioforms. Listen to `audioSample` URLs to audition voices before committing.

```python
def query_voices(query: str = "", filters: list = None) -> list:
    body = {
        "query": query,
        "filters": filters or [],
        "forceApplyFilters": True,
        "pageLimit": 10,
    }
    resp = requests.post(f"{BASE}/assets/voices/query", headers=HEADERS, json=body)
    resp.raise_for_status()
    voices = resp.json()["data"]["voices"]
    for v in voices:
        print(f"{v['alias']:20} {v.get('gender','?'):8} {v.get('accent','?'):20} provider={v.get('provider','?')}")
    return voices

# ElevenLabs British male voices — use filters, leave query empty
query_voices(
    filters=[
        {"in": {"provider": ["elevenlabs"]}},
        {"in": {"gender": ["male"]}},
        {"in": {"accent": ["british"]}},
    ]
)

# Hume or Cartesia Australian female voices
query_voices(
    filters=[
        {"in": {"provider": ["hume", "cartesia"]}},
        {"in": {"gender": ["female"]}},
        {"in": {"accent": ["australian"]}},
    ]
)

# Any calm, storytelling voice in English
query_voices(query="calm storytelling english")
```

**Filter fields:**  
`provider` · `gender` · `accent` · `language` · `ageBracket` · `alias`

Use `alias` to fetch specific known voices by name:
```python
query_voices(filters=[{"in": {"alias": ["rodney", "cicely"]}}])
```

**Provider values:** `elevenlabs`, `hume`, `cartesia`, `azure`, `google`, `openai`, `polly`, `speechify`, `wellsaid`, …  
**Gender values:** `male`, `female`, `character`  
**Accent examples:** `british`, `australian`, `american`, `irish`, `scottish`, `canadian`, …

---

### 3. Query the Sound Template Library

Browse AudioStack's music library for background tracks. Each template is a production-ready music bed that the audioform engine can automatically edit to match your spot length (SmartFit). Use `alias` from the results in audioform `soundTemplateAlias`.

```python
def query_sound_templates(query: str = "", filters: list = None) -> list:
    body = {
        "query": query,
        "filters": filters or [],
        "forceApplyFilters": True,
        "pageLimit": 10,
    }
    resp = requests.post(f"{BASE}/assets/sound-templates/query", headers=HEADERS, json=body)
    resp.raise_for_status()
    templates = resp.json()["data"]["soundTemplates"]
    for t in templates:
        meta = t.get("meta", {})
        print(f"{t['alias']:30} genre={meta.get('genre',[])} energy={meta.get('energy',[])} bpm={meta.get('bpm','?')}")
    return templates

# Upbeat pop for a 30s ad
query_sound_templates(
    query="upbeat energetic",
    filters=[
        {"in": {"genre": ["pop"]}},
        {"in": {"energy": ["high"]}},
    ]
)

# Calm ambient for a news bulletin
query_sound_templates(query="calm ambient news")

# Jazz with piano
query_sound_templates(
    filters=[
        {"in": {"genre": ["jazz"]}},
        {"in": {"instrument": ["piano"]}},
    ]
)
```

**Filter fields:** `genre` · `energy` · `instrument` · `mood` · `tempo` · `key` · `holidays` · `bpm` · `alias`  
**Energy values:** `high`, `medium`, `low`, `variable`  
**Genre examples:** `pop`, `jazz`, `classical`, `ambient`, `electronicDance`, `rockSoul`, `folkCountry`, …

---

### 4. Generate an Ad from a Product Description (Creator/Brief)

The fastest path to a finished audio ad. Give it a product description and it writes the script with AI, selects a voice, adds background music, and returns a rendered audio file — no audioform assembly required. Use this when you want a complete ad with minimal configuration.

The response wraps ads under `data.audioforms`; each item has an `audioformId` at status 202, so poll `GET /audioforms/{id}` for the final URL.

```python
def create_ad_from_brief(
    product_name: str,
    product_description: str,
    ad_length: int = 30,       # 10, 15, 20, 30, or 40
    call_to_action: str = "",
    target_audience: str = "",
    num_ads: int = 1,
) -> list:
    body = {
        "brief": {
            "script": {
                "productName": product_name,
                "productDescription": product_description,
                "adLength": ad_length,
                "callToAction": call_to_action,
                "targetAudience": target_audience,
            },
            "voices": [{"alias": None, "voicePreset": "expressive"}],
            "sounds": {
                "soundDesign": [{"alias": None, "useSmartFit": True}]
            },
        },
        "numAds": num_ads,
    }
    resp = requests.post(f"{BASE}/creator/brief", headers=HEADERS, json=body)
    resp.raise_for_status()
    ads = resp.json()["data"]["audioforms"]
    for ad in ads:
        af_id = ad["audioformId"]
        result = poll_audioform(af_id)
        url = result.get("result", {}).get("delivery", {}).get("uri")
        print(f"Ad {af_id}: {url}")
    return ads

create_ad_from_brief(
    product_name="Acme Coffee Roasters",
    product_description=(
        "Premium single-origin coffee beans, roasted to order and delivered in 48 hours. "
        "Perfect for home baristas who demand café quality without leaving the house."
    ),
    ad_length=30,
    call_to_action="Order today at acmecoffee.com",
    target_audience="Home coffee enthusiasts aged 25-45",
)
```

**To use your own script** instead of AI-generated:

```python
body["brief"]["script"] = {
    "productName": "Acme Coffee Roasters",
    "scriptText": "Great coffee, delivered. Order at acmecoffee.com.",
    "adLength": 30,
}
```

---

### 5. Build a Multivoice Audioform

Use this when you need full control over the production: specific voices, music choice, precise spot duration, or a multi-speaker conversation. The audioform is the core building block — you define assets (voices, TTS text, music), arrange them in a section, and set constraints to hit an exact length. Renders asynchronously; poll for the result.

### Poll helper

The GET endpoint requires a `version` header matching the audioform version you submitted.

```python
def poll_audioform(audioform_id: str, timeout: int = 120) -> dict:
    url = f"{BASE}/audioforms/{audioform_id}"
    headers = {**HEADERS, "version": "4"}
    for _ in range(timeout // 3):
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()["data"]
        elif resp.status_code == 202:
            time.sleep(3)
        else:
            resp.raise_for_status()
    raise TimeoutError(f"Audioform {audioform_id} did not complete in {timeout}s")
```

### Multivoice 15-second spot with music

```python
def build_multivoice_ad(
    text_host: str,
    text_guest: str,
    voice_host: str,    # e.g. "rodney"
    voice_guest: str,   # e.g. "cicely"
    music_alias: str,   # from sound template query
    spot_duration: float = 15.0,
) -> str:
    """Returns the audio URL."""
    audioform = {
        "header": {"version": "4"},
        "assets": {
            # TTS assets — set anchor for reproducibility across re-renders
            "tts_host": {
                "type": "tts",
                "text": text_host,
                "voiceRef": "voice_host",
                "anchor": f"host:{text_host[:40]}",   # same text+voice → same audio
            },
            "tts_guest": {
                "type": "tts",
                "text": text_guest,
                "voiceRef": "voice_guest",
                "anchor": f"guest:{text_guest[:40]}",
            },
            # Voice definitions
            "voice_host": {
                "type": "voice",
                "voiceAlias": voice_host,
                "voicePreset": "expressive",
            },
            "voice_guest": {
                "type": "voice",
                "voiceAlias": voice_guest,
                "voicePreset": "expressive",
            },
            # Background music
            "bg_music": {
                "type": "soundTemplate",
                "soundTemplateAlias": music_alias,
                "segment": "main",
            },
        },
        "production": {
            "arrangement": {
                "sections": [{
                    "layers": [{
                        "clips": [
                            {"assetRef": "tts_host", "marginStart": 0},
                            {"assetRef": "tts_guest", "marginStart": 0},
                        ],
                        "alignment": "start",
                    }],
                    "soundTemplateRef": "bg_music",
                    "smartFit": True,           # music edits cleanly to spot length
                    "forcedDuration": spot_duration,
                }],
            },
            # Time constraint: fit both TTS clips within 14s of the 15s spot
            "constraints": [{
                "type": "timeConstraint",
                "assets": ["tts_host", "tts_guest"],
                "groupTargetDuration": spot_duration - 1,
                "targetDurationSpeedUpLimit": 1.5,
                "targetDurationSlowDownLimit": 1.0,
            }],
            "mixingPreset": "balanced",
        },
        "delivery": {
            "encoderPreset": "mp3",
            "loudnessPreset": "streaming",
            "public": True,
        },
    }

    resp = requests.post(f"{BASE}/audioforms/", headers=HEADERS, json={"audioform": audioform})
    resp.raise_for_status()
    audioform_id = resp.json()["data"]["audioformId"]
    print(f"Audioform submitted: {audioform_id}")

    result = poll_audioform(audioform_id)
    url = result["result"]["delivery"]["uri"]
    print(f"Audio ready: {url}")
    return url

# Example
url = build_multivoice_ad(
    text_host="Welcome to the Acme Coffee Hour. Today we're talking about single-origin beans.",
    text_guest="Absolutely. The difference in flavour is remarkable. You can taste the terroir.",
    voice_host="rodney",
    voice_guest="cicely",
    music_alias="dusty_jeans",
    spot_duration=15.0,
)
```

### TTS Anchor — reproducibility explained

Set `anchor` on any TTS asset. Re-submitting an audioform with the **same text, same voice, and same anchor** will produce **identical audio** — useful for versioning ads where only the music changes.

```python
# First render: set anchor
"tts_host": {"type": "tts", "text": "...", "voiceRef": "voice_host", "anchor": "v1-host-line1"}

# Later render with a different music track — voice stays byte-identical
"tts_host": {"type": "tts", "text": "...", "voiceRef": "voice_host", "anchor": "v1-host-line1"}
```

If you omit `anchor`, the API generates a unique one for you (visible in the result) that you can copy for future renders.

---

### 6. Create a News Bulletin (Story)

Use the story endpoint for multi-segment long-form content: news bulletins, podcasts, narrated sequences. You define a cast of speakers and a background music bed once, then provide chapters — each with its own foreground text and background layer. The API renders each chapter as a separate audio file. Async: submit, then poll for completion.

```python
def create_news_bulletin(
    title: str,
    items: list[dict],      # [{"headline": "...", "body": "..."}]
    voice_alias: str = "rodney",
    music_alias: str = "news_ambient",
) -> list:
    """
    Each item becomes a chapter. Returns list of audio URLs.
    items = [{"headline": "Rain expected in Lisbon", "body": "Bring an umbrella..."}]
    """
    chapters = []
    for item in items:
        chapters.append({
            "title": item["headline"],
            "narratives": [{
                "foreground": [
                    {"text": item["headline"], "speakerIdentifier": "anchor"},
                    {"text": item["body"], "speakerIdentifier": "anchor"},
                ],
                "background1": [{
                    "soundDesignIdentifier": "bg",
                    "duration": None,       # run for full foreground duration
                    "useSmartFit": True,
                }],
            }],
        })

    body = {
        "story": {
            "title": title,
            "voices": [{
                "alias": voice_alias,
                "speakerIdentifier": "anchor",
                "voicePreset": "expressive",
            }],
            "sounds": {
                "soundDesigns": [{
                    "soundDesignIdentifier": "bg",
                    "type": "asset",
                    "alias": music_alias,
                }]
            },
            "chapters": chapters,
            "delivery": {"encoderPreset": "mp3", "public": True},
        }
    }

    resp = requests.post(f"{BASE}/creator/story", headers=HEADERS, json=body)
    resp.raise_for_status()
    story_id = resp.json()["data"]["storyId"]
    print(f"Story submitted: {story_id}")

    # Poll for completion — correct path is /creator/story/{storyId}
    audioform_ids = []
    for _ in range(60):
        poll = requests.get(f"{BASE}/creator/story/{story_id}", headers=HEADERS)
        if poll.status_code == 200:
            data = poll.json()["data"]
            if data.get("statusCode") == 200:
                audioform_ids = [
                    af["header"]["audioformId"]
                    for af in data.get("audioforms", [])
                    if af.get("header", {}).get("audioformId")
                ]
                break
        time.sleep(5)
    else:
        raise TimeoutError(f"Story {story_id} did not complete")

    urls = []
    for af_id in audioform_ids:
        result = poll_audioform(af_id)
        urls.append(result.get("result", {}).get("delivery", {}).get("uri"))
    print(f"Story complete — {len(urls)} segments")
    return urls

urls = create_news_bulletin(
    title="Newsify Daily Bulletin",
    items=[
        {"headline": "Weather update", "body": "Rain expected in Lisbon today. Bring an umbrella."},
        {"headline": "Markets", "body": "European stocks opened higher on positive inflation data."},
        {"headline": "Sport", "body": "Portugal defeated Spain 2-1 in last night's friendly."},
    ],
    voice_alias="rodney",
    music_alias="news_ambient",
)
```

---

### 7. Batch Audioforms for Versioning

Generate a large number of audio variants in a single API call — up to 1000 audioforms submitted together and rendered in parallel. The canonical use case is versioning: same script across multiple voices, multiple spot lengths, or different music beds. Each item in the batch gets a name you define, making results easy to map back to your variants.

```python
def submit_batch(variants: list[dict]) -> str:
    """
    variants: list of {"name": str, "audioform": dict}
    Returns batchId.
    """
    resp = requests.post(
        f"{BASE}/audioforms/batches",
        headers=HEADERS,
        json={"items": variants}
    )
    resp.raise_for_status()
    batch_id = resp.json()["data"]["batchId"]
    print(f"Batch submitted: {batch_id}")
    return batch_id

def poll_batch(batch_id: str, timeout: int = 300) -> list:
    """Polls until complete. Returns list of (name, url) tuples."""
    for _ in range(timeout // 5):
        resp = requests.get(f"{BASE}/audioforms/batches/{batch_id}", headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()["data"]
        if data["status"] == "complete":
            results = []
            for item in data["items"]:
                result = item.get("audioformResult") or {}
                url = result.get("delivery", {}).get("uri")
                results.append({"name": item["name"], "url": url, "status": item.get("audioformStatus")})
            return results
        time.sleep(5)
    raise TimeoutError(f"Batch {batch_id} did not complete in {timeout}s")

# Build variants: same script, 3 voices, 2 spot lengths
def make_audioform(text: str, voice_alias: str, duration: float, music_alias: str) -> dict:
    return {
        "header": {"version": "4"},
        "assets": {
            "tts0": {"type": "tts", "text": text, "voiceRef": "v0", "anchor": f"{voice_alias}:{text[:30]}"},
            "v0": {"type": "voice", "voiceAlias": voice_alias, "voicePreset": "expressive"},
            "bg": {"type": "soundTemplate", "soundTemplateAlias": music_alias, "segment": "main"},
        },
        "production": {
            "arrangement": {
                "sections": [{
                    "layers": [{"clips": [{"assetRef": "tts0"}], "alignment": "start"}],
                    "soundTemplateRef": "bg",
                    "smartFit": True,
                    "forcedDuration": duration,
                }]
            },
            "constraints": [{
                "type": "timeConstraint",
                "assets": ["tts0"],
                "groupTargetDuration": duration - 1,
                "targetDurationSpeedUpLimit": 1.5,
                "targetDurationSlowDownLimit": 1.0,
            }],
            "mixingPreset": "balanced",
        },
        "delivery": {"encoderPreset": "mp3", "loudnessPreset": "streaming", "public": True},
    }

script = "Great coffee, delivered to your door in 48 hours. Order at acmecoffee.com."
voices = ["rodney", "cicely", "isaac"]
durations = [15.0, 30.0]
music = "dusty_jeans"

variants = [
    {
        "name": f"{voice}-{int(dur)}s",
        "audioform": make_audioform(script, voice, dur, music),
    }
    for voice in voices
    for dur in durations
]

batch_id = submit_batch(variants)
results = poll_batch(batch_id)
for r in results:
    print(f"{r['name']:20} {r['status']:10} {r['url']}")
```

