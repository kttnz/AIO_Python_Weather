# AIO Python Weather

An all-in-one Python weather application that reports current conditions,
forecasts, alerts, and radar imagery using data from NOAA and other public
APIs.

## Setup

Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the application from the command line:

```bash
python weather_app.py
```

If automatic location detection fails (e.g., due to network restrictions),
provide your coordinates via environment variables:

```bash
export LAT=32.7767
export LON=-96.7970
python weather_app.py
```
