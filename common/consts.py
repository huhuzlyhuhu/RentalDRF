from concurrent.futures.thread import ThreadPoolExecutor

import boto3
import qiniu

MAX_READ_SIZE = 64 * 1024

QINIU_ACCESS_KEY = 'KarvlHfUdoG1mZNSfDVS5Vh3nae2jUZumTBHK-PR'
QINIU_SECRET_KEY = 'SFPFkAn5NENhdCMqMe9wd_lxGHAeFR5caXxPTtt7'
QINIU_BUCKET_NAME = 'zufangwang'

AUTH = qiniu.Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)

# AWS3_REGION = 'region_name'
# AWS3_AK = 'access_key'
# AWS3_SK = 'secret_key'
# AWS3_BUCKET = 'bucket_name'
#
# S3 = boto3.client('s3', region_name=AWS3_REGION,
#                   aws_access_key_id=AWS3_AK, aws_secret_access_key=AWS3_SK)

# sysbench ---> 测试整机性能的工具
MAX_THREAD_WORKERS = 64
EXECUTOR = ThreadPoolExecutor(max_workers=MAX_THREAD_WORKERS)
