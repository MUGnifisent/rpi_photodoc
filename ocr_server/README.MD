# OCR Server

A standalone HTTP server that provides OCR (Optical Character Recognition) services using EasyOCR.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install flask flask-cors easyocr pyyaml
   ```

2. **Run the server:**
   ```bash
   python ocr_server.py
   ```

3. **Server will start on:** `http://0.0.0.0:8080`

That's it! The server is now ready to process OCR requests.

## Configuration (Optional)

Create `ocr_server_config.yaml` in the same directory as `ocr_server.py` to customize settings:

```yaml
server:
  host: '0.0.0.0'
  port: 8080
  debug: false

ocr:
  languages: ['uk', 'en']  # Ukrainian and English
  detail: 0                # 0 = text only, 1 = with coordinates
  paragraph: true
  workers: 0               # 0 = auto

upload:
  max_file_size: 16777216  # 16MB
  allowed_extensions: ['png', 'jpg', 'jpeg', 'webp', 'tiff', 'bmp']

cors:
  enabled: true
  origins: '*'             # In production, specify allowed domains

logging:
  level: 'INFO'
  save_requests: false     # Set to true for debugging
```

## API Endpoints

### Health Check
```bash
GET /health
```
Returns server health status and OCR readiness.

### Server Information
```bash
GET /info
```
Returns server version, supported languages, and configuration.

### OCR Processing
```bash
POST /ocr
```
Upload an image file for OCR processing.

**Example using curl:**
```bash
curl -X POST -F "image=@photo.jpg" http://localhost:8080/ocr
```

**Response:**
```json
{
  "success": true,
  "text": "Extracted text from the image...",
  "length": 123,
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

## Using with RPi OCR Formatter

1. Start the OCR server on a machine (can be the same RPi or a different server)
2. In the main application settings, choose "Remote OCR Server"
3. Set the OCR Server URL to: `http://[server-ip]:8080/ocr`
4. Save settings

The main application will now send images to this server for processing instead of using local OCR.

## Production Notes

- For production use, consider:
  - Setting `host: '127.0.0.1'` if running on the same machine
  - Specifying allowed CORS origins instead of using `'*'`
  - Using a reverse proxy (nginx) for HTTPS
  - Running with a production WSGI server (gunicorn, uWSGI)
  - Setting up proper firewall rules

## Troubleshooting

**Server won't start:**
- Check if port 8080 is already in use
- Ensure all dependencies are installed
- Check the console for error messages

**OCR not working:**
- The first request may be slow as EasyOCR downloads models
- Check `/health` endpoint to verify OCR is initialized
- Ensure uploaded images are in supported formats

**Connection issues:**
- Verify the server IP and port are correct
- Check firewall settings if accessing from another machine
- Ensure CORS is properly configured for cross-origin requests

## Performance Tips

- The first OCR request will be slower as EasyOCR loads models
- For GPU acceleration, install CUDA and set `gpu=True` in the code
- Adjust `workers` setting based on your CPU cores
- Consider running multiple server instances behind a load balancer for high load