import os
import io
import uuid

import requests
from flask import (
    Flask,
    request,
    abort
)
from google.cloud import storage
from linebot import (
    LineBotApi,
    WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    ImageMessage,
    VideoMessage
)


BUCKET_NAME = os.environ["BUCKET_NAME"]
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
SLACK_TOKEN = os.environ["SLACK_TOKEN"]

port = int(os.getenv("PORT", 5000))
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)
client = storage.Client()
bucket = client.get_bucket(BUCKET_NAME)

app = Flask(__name__)


@app.route("/", methods=['GET'])
def health_check():
    return "OK"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="画像/動画を送信してください。")
    )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    upload(f"{message_id}.jpeg", io.BytesIO(message_content.content))
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="送信ありがとうございます！")
    )
    send_slack(message_id, get_profile(event.source.user_id), f"https://storage.googleapis.com/{BUCKET_NAME}/{message_id}.jpeg")


@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    upload(f"{message_id}.mp4", io.BytesIO(message_content.content))
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="送信ありがとうございます！")
    )
    send_slack(message_id, get_profile(event.source.user_id), f"https://storage.googleapis.com/{BUCKET_NAME}/{message_id}.mp4")


def get_profile(user_id):
    return line_bot_api.get_profile(user_id)


def upload(filename, io_bytes):
    io_bytes.seek(0)
    blob = bucket.blob(filename)
    blob.upload_from_string(data=io_bytes.getvalue(), content_type='application/octet-stream')


def send_slack(message_id, profile, content_url):
    payload = {
        "token": SLACK_TOKEN,
        "channel": "image_bot",
        "username": "ImageBot",
        "text": f"Uploaded media content.\nDisplayName: {profile.display_name}\nMessageId: {message_id}\n\n{content_url}"
    }
    res = requests.post("https://slack.com/api/chat.postMessage", payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
