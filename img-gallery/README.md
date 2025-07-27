```
python -m venv venv
source venv/bin/activate
pip install Pillow tqdm # for the thumbnail generator
pip install fastapi uvicorn Jinja2 # for the server
python create_downsized_images.py -i ./imgs -o ./imgs-small -d 300 # generate the thumbnails
uvicorn gallery_server:app --reload # test server
uvicorn gallery_server:app --host 0.0.0.0 --port 8000 --reload # deploy server
```
