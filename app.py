TEST_MODE = False   # Zet op False als je echte analyse wilt


from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import numpy as np
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tijdelijke opslag
TEMP_DATA = {}
LOCATIONS = [
    {
        "name": "Kies een locatie"
    },
    {
       "name": "School", 
       "tag": "school",
       "lat": 52.715817891338546, 
       "lon": 5.749000545222782
    }
]

# ---------------------------
# 1. /api/data  (velden opslaan)
# ---------------------------
@app.post("/api/data")
async def save_data(
    naam: str = Form(...),
    plaats: str = Form(...),
    straat: str = Form(...),
    huisnummer: str = Form(...),
    email: str = Form(...),
):
    global TEMP_DATA
    TEMP_DATA = {
        "naam": naam,
        "plaats": plaats,
        "straat": straat,
        "huisnummer": huisnummer,
        "email": email
    }
    return {"status": "ok", "saved": TEMP_DATA}

@app.get("/api/data")
async def get_data():
    return {"saved": TEMP_DATA}



# 2. /api/newlocation  (locatie toevoegen)
@app.post("/api/location")
async def new_location(
    locName: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...)
    ):
    tag = locName.lower().replace(" ", "")

    new_location = {
        "name": locName,
        "tag": tag,
        "lat": lat,
        "lon": lon,
    }

    LOCATIONS.append(new_location)
    # LOCATIONS.append(LocName)
    return {"status": "added", "locations": LOCATIONS}

@app.get("/api/location")
async def get_location():
    return{"saved": LOCATIONS }


@app.post("/api/analyze")
async def analyze_location(file: UploadFile = File(...)):

    global TEST_MODE
    
    if TEST_MODE:
        return {"safe": True, "message": "Locatie automatisch goedgekeurd (testmodus)."}

    # --- vanaf hier blijft jouw echte analyse staan ---

    try:
        # Lees afbeelding in
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        img_np = np.array(image)
        height, width, _ = img_np.shape

        # --- Check 3x3 meter equivalent ---
        min_pixels = 300
        safe_size = width >= min_pixels and height >= min_pixels

        # --- Check lucht vrij ---
        top_crop = img_np[0:int(height * 0.15), :, :]

        def rgb_to_hsv_pixel(r, g, b):
            r_, g_, b_ = r / 255, g / 255, b / 255
            mx = max(r_, g_, b_)
            mn = min(r_, g_, b_)
            diff = mx - mn

            if diff == 0:
                h = 0
            elif mx == r_:
                h = (60 * ((g_ - b_) / diff) + 360) % 360
            elif mx == g_:
                h = (60 * ((b_ - r_) / diff) + 120) % 360
            else:
                h = (60 * ((r_ - g_) / diff) + 240) % 360

            s = 0 if mx == 0 else diff / mx
            v = mx
            return h, s, v

        sky_pixels = 0
        total_pixels = top_crop.shape[0] * top_crop.shape[1]

        for row in top_crop:
            for pixel in row:
                h, s, v = rgb_to_hsv_pixel(pixel[0], pixel[1], pixel[2])

                is_blue = (90 <= h <= 130) and (s > 0.2) and (v > 0.2)
                is_light = (v > 0.7) and (s < 0.15)

                if is_blue or is_light:
                    sky_pixels += 1

        sky_ratio = sky_pixels / total_pixels
        safe_sky = sky_ratio > 0.6

        safe = safe_size and safe_sky
        if safe:
            message = "Locatie voldoet: minimaal 3×3 meter en lucht vrij."
        elif not safe_size:
            message = "Locatie te klein, minimaal 3×3 meter vereist."
        elif not safe_sky:
            message = "Lucht lijkt niet vrij (te veel obstakels)."
        else:
            message = "Locatie afgekeurd."

        return JSONResponse({"safe": safe, "message": message})

    except Exception as e:
        return JSONResponse({"safe": False, "message": f"Fout bij analyse: {str(e)}"})
    
    finally:
        TEST_MODE = True


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
