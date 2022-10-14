from django.http import HttpResponse
from django.shortcuts import redirect

from common.captcha import Captcha
from common.utils import gen_captcha_text


def index(request):
    return redirect('/static/html/index.html')


def get_captcha(request):
    instance = Captcha.instance()
    text = gen_captcha_text()
    data = instance.generate(text)
    return HttpResponse(data, content_type='image/png')
