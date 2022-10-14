"""
项目常用工具函数
"""
import datetime
import hashlib
import io
import ujson
import os
import random
import uuid
from functools import wraps, partial

import qrcode
import requests
from PIL.Image import Image

from common.consts import *
from zufang import app


def get_ip_address(request):
    """获得请求的IP地址"""
    ip = request.META.get('HTTP_X_FORWARDED_FOR', None)
    return ip or request.META['REMOTE_ADDR']


def to_md5_hex(data):
    """生成MD5摘要"""
    if type(data) != bytes:
        if type(data) == str:
            data = data.encode()
        elif type(data) == io.BytesIO:
            data = data.getvalue()
        else:
            data = bytes(data)
    return hashlib.md5(data).hexdigest()


def gen_mobile_code(length=6):
    """生成指定长度的手机验证码"""
    return ''.join(random.choices('0123456789', k=length))


def gen_captcha_text(length=4):
    """生成指定长度的图片验证码文字"""
    return ''.join(random.choices(
        '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
        k=length)
    )


def make_thumbnail(image_file, path, size, keep=True):
    """生成缩略图"""
    image = Image.open(image_file)
    origin_width, origin_height = image.size
    if keep:
        target_width, target_height = size
        w_rate, h_rate = target_width / origin_width, target_height / origin_height
        rate = w_rate if w_rate < h_rate else h_rate
        width, height = int(origin_width * rate), int(origin_height * rate)
    else:
        width, height = size
    image.thumbnail((width, height))
    image.save(path)


def gen_qrcode(data):
    """生成二维码"""
    image = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


@app.task
def send_sms_by_luosimao(tel, message):
    """发送短信（调用螺丝帽短信网关）"""
    resp = requests.post(
        url='http://sms-api.luosimao.com/v1/send.json',
        auth=('api', 'key-d752503b8db92317a2642771cec1d9b0'),
        data={
            'mobile': tel,
            'message': message
        },
        timeout=10,
        verify=False)
    return ujson.loads(resp.content)


@app.task
def upload_file_to_qiniu(file_path, filename):
    """将文件上传到七牛云存储"""
    token = AUTH.upload_token(QINIU_BUCKET_NAME, filename)
    return qiniu.put_file(token, filename, file_path)


@app.task
def upload_stream_to_qiniu(file_stream, filename, size):
    """将数据流上传到七牛云存储"""
    token = AUTH.upload_token(QINIU_BUCKET_NAME, filename)
    result, *_ = qiniu.put_stream(token, filename, file_stream, None, size)
    return result


# def url_from_key(file_key):
#     """通过文件的key拼接访问URL"""
#     return f'https://s3.{AWS3_REGION}.amazonaws.com.cn/{AWS3_BUCKET}/{file_key}'
#
#
# def s3_upload_file(file):
#     """上传文件到亚马逊S3"""
#     hasher = hashlib.md5()
#     file_name, file_size = file.name, file.size
#     key = uuid.uuid4() + "." + os.path.splitext(file_name)[1]
#     multipart_upload_init_info = S3.create_multipart_upload(
#         ACL='public-read', Bucket=AWS3_BUCKET, Key=key,
#         Expires=(datetime.datetime.today() + datetime.timedelta(days=1)),
#     )
#     upload_id = multipart_upload_init_info['UploadId']
#     part_key = multipart_upload_init_info['Key']
#
#     uploaded_size, chunks_number, parts_list = 0, 1, []
#     while uploaded_size <= file_size:
#         chunks = file.read(MAX_READ_SIZE)
#         hasher.update(chunks)
#         chunks_response = S3.upload_part(
#             Body=chunks, Bucket=AWS3_BUCKET, Key=part_key,
#             PartNumber=chunks_number, UploadId=upload_id
#         )
#         parts_list.append({
#             'ETag': chunks_response['ETag'],
#             'PartNumber': chunks_number
#         })
#         chunks_number = chunks_number + 1
#         uploaded_size += MAX_READ_SIZE
#     S3.complete_multipart_upload(
#         Bucket=AWS3_BUCKET, Key=part_key,
#         UploadId=upload_id, MultipartUpload={'Parts': parts_list}
#     )
#     body_md5 = hasher.hexdigest()
#     return url_from_key(key), body_md5


def run_in_thread_pool(*, callbacks=(), callbacks_kwargs=()):
    """将函数放入线程池执行的装饰器"""

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            future = EXECUTOR.submit(func, *args, **kwargs)
            for index, callback in enumerate(callbacks):
                try:
                    kwargs = callbacks_kwargs[index]
                except IndexError:
                    kwargs = None
                fn = partial(callback, **kwargs) if kwargs else callback
                future.add_done_callback(fn)
            return future

        return wrapper

    return decorator
