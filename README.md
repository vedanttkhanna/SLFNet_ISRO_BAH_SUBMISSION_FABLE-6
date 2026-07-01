# SLFNet: Sentinel-LISS IV Fusion Network

A multimodal generative AI pipeline for cloud removal and reconstruction in LISS-IV satellite imagery, developed for ISRO Bharatiya Antariksh Hackathon 2026 (PS2).

**Team:** Fable-6  
**Institution:** Delhi Technological University  
**Members:** Vedant Khanna, Ritwik Jain, Shreshth Rai, Paarth Gupta

---

## Overview

Persistent cloud cover is a major challenge in optical remote sensing, particularly over tropical and monsoon-affected regions of India. SLFNet addresses this by proposing a multimodal ensemble pipeline that combines a diffusion-based cloud removal model (DiffCR) with a SAR-informed regression model (UnCRtainTS-NAFNet), fused via a cross-attention module trained on custom LISS-IV paired data.

Unlike existing approaches that target Sentinel-2 (13-band, 10m), this pipeline is designed specifically for ISRO's LISS-IV sensor (3-band G/R/NIR, 5.8m resolution), for which no public cloud-removal benchmark dataset currently exists.

---

## Architecture

The pipeline consists of three components.

**DiffCR (Model Branch 1)**  
A conditional denoising diffusion model. Three LISS-IV optical acquisitions at different timestamps are concatenated into a 9-channel condition tensor and passed to a double-encoder backbone. A denoising UNet with split cross-attention learns the reverse diffusion process. DPM-Solver reduces inference from approximately 1000 DDPM steps to 20, making the model computationally practical. Output is a 3-channel cloud-free optical image.

**UnCRtainTS-NAFNet (Model Branch 2)**  
A deterministic regression model. Takes a 15-channel tensor per timestamp consisting of 2-channel Sentinel-1 SAR (VV, VH) and 13-channel optical data. A dual-encoder with shared downsampling processes main features and SAR-guided condition features in parallel; the decoder fuses both via additive skip connections. Single forward pass, deterministic inference.

**SLFNet Fusion Module (Model Branch 3)**  
The core novelty. Takes a 10-channel fusion input: DiffCR prediction (3ch), NAFNet prediction (3ch), cloudy optical (3ch), and SAR (1ch). A CNN encoder extracts feature maps from each prediction; cross-attention between them allows the network to learn per-region and per-scale which model to trust. A convolutional decoder produces the fused cloud-free image and a pixel-wise confidence map showing which model dominated each spatial region. Approximately 500K trainable parameters, designed to converge on limited paired data.

---

## Dataset

**Primary optical data:** LISS-IV (Resourcesat-2A), 3-band (G, R, NIR), 5.8m resolution, sourced from Bhoonidhi (bhoonidhi.nrsc.gov.in). Covers 10 regions across India at 5 timestamps each, including a mix of cloudy and cloud-free acquisitions spanning different geological topographies and seasonal conditions. Approximately 2 lakh 256x256px patches generated from raw scenes.

**Auxiliary SAR data:** Sentinel-1 GRD, VV and VH polarization, IW mode, fetched via Google Earth Engine (`COPERNICUS/S1_GRD`), reprojected and pixel-aligned to each LISS-IV scene.

**Fusion training target:** Cloudy LISS-IV (3-band RGB) as input, cloud-free LISS-IV (3-band RGB) as reference.

---

## Results (so far)

Evaluated on held-out LISS-IV data after 10,000 training steps (batches, not epochs).

| Model | PSNR | SSIM |
|---|---|---|
| Cloudy input (baseline) | 8.38 dB | 0.1013 |
| NafNet (GAN) | 9.88 dB | 0.1146 |
| DiffCR (Diffusion) | 11.71 dB | 0.0561 |
| SLFNet (ours) | 16.83 dB | 0.3146 |

SLFNet achieves +6.95 PSNR and +0.2 SSIM over the previous best after only 10,000 training steps. Training is actively continuing.

---

## Repository Structure

```
SLFNet/
    bhoonidhi_scraper.py       Automated LISS-IV data collection via Bhoonidhi API
    data/                      Dataset preparation and patch extraction scripts
    models/
        diffcr/                DiffCR model branch
        uncrtaints_nafnet/     UnCRtainTS-NAFNet model branch
        slfnet/                Fusion module (cross-attention + convolutional decoder)
    training/                  Training scripts for all three components
    evaluation/                Evaluation scripts (PSNR, SSIM, MAE, confidence maps)
    checkpoints/               Model checkpoints
```

---

## bhoonidhi_scraper.py

Automates programmatic data collection of LISS-IV cloudy and clear scene pairs from Bhoonidhi using their STAC-compliant API.

**Requirements:**

- A registered Bhoonidhi account (register at bhoonidhi.nrsc.gov.in)
- Your account's static public IPv4 address whitelisted by Bhoonidhi (email bhoonidhi@nrsc.gov.in to request this)
- Python dependencies: `requests`, `tqdm`

**Installation:**

```bash
pip install requests tqdm
```

**Configuration:**

Open `bhoonidhi_scraper.py` and set:

```python
USER_ID  = "your_bhoonidhi_user_id"
PASSWORD = "your_bhoonidhi_password"
```

Adjust `REGIONS`, `DATE_START`, `DATE_END`, `CLOUDY_MIN`, and `CLEAR_MAX` as needed.

**Usage:**

```bash
python bhoonidhi_scraper.py
```

The script authenticates using Bearer token auth (token refreshed automatically every 18 minutes to avoid expiry), searches for LISS-IV scenes over each configured region filtered by cloud cover percentage, and downloads BAND2.tif, BAND3.tif, BAND4.tif for each scene into a structured output directory.

**Output structure:**

```
liss4_scenes/
    hyderabad_cloudy/
        <scene_id>/
            BAND2.tif
            BAND3.tif
            BAND4.tif
            BAND_META.txt
    hyderabad_clear/
        ...
    pune_cloudy/
        ...
```

**Note on the collection name:** The script uses `"LISS-IV-MX"` as the STAC collection identifier. If searches return zero results, check available collections first:

```python
import requests
r = requests.get(
    "https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/stac/collections",
    headers={"Authorization": f"Bearer {token}"}
)
print(r.json())
```

---

## Tech Stack

Python, PyTorch, React, Xarray, NumPy, Rasterio, GDAL, PostGIS, QGIS, Google Earth Engine, Matplotlib, Bhoonidhi

---

## References

1. Xuechao Zou et al. DiffCR: A Fast Conditional Diffusion Framework for Cloud Removal from Optical Satellite Images. IEEE TGRS 2024.
2. Patrick Ebel et al. UnCRtainTS: Uncertainty Quantification for Cloud Removal in Optical Satellite Time Series. CVPRW 2023.
3. Jin Ning et al. Cloud Removal Advances: A Comprehensive Review and Analysis for Optical Remote Sensing Images.
4. Vishnu Sarukkai et al. Cloud Removal from Satellite Images using Spatiotemporal Generator Networks.
