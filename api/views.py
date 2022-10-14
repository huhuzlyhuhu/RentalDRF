import datetime
import os
import random

import jwt
import ujson
from django.core.cache import caches
from django.db.models import Prefetch, Q
from django.db.transaction import atomic
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from django_redis import get_redis_connection
from rest_framework.decorators import api_view, action
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from api.consts import MAX_PHOTO_SIZE, FILE_UPLOAD_SUCCESS, FILE_SIZE_EXCEEDED, \
    CODE_TOO_FREQUENCY, MOBILE_CODE_SUCCESS, INVALID_TEL_NUM, USER_LOGIN_SUCCESS, \
    USER_LOGIN_FAILED, INVALID_LOGIN_INFO
from api.helpers import EstateFilterSet, HouseInfoFilterSet, DefaultResponse, \
    LoginRequiredAuthentication, RbacPermission
from api.serializers import DistrictSimpleSerializer, DistrictDetailSerializer, \
    AgentCreateSerializer, AgentDetailSerializer, AgentSimpleSerializer, \
    HouseTypeSerializer, TagSerializer, EstateCreateSerializer, \
    EstateDetailSerializer, EstateSimpleSerializer, HouseInfoDetailSerializer, \
    HousePhotoSerializer, HouseInfoCreateSerializer, HouseInfoSimpleSerializer, \
    UserCreateSerializer, UserUpdateSerializer, UserSimpleSerializer, RoleSimpleSerializer
from common.models import District, Agent, HouseType, Tag, User, LoginLog, \
    HousePhoto, Estate, HouseInfo
from common.utils import gen_mobile_code, send_sms_by_luosimao, to_md5_hex, \
    get_ip_address, upload_stream_to_qiniu
from common.validators import check_tel, check_username, check_email
from zufang.settings import SECRET_KEY


@api_view(('GET', ))
def get_payment_page(request, houseid):
    pass
    # alipay = AliPay(
    #     appid=settings.ALIPAY_APPID,
    #     app_notify_url=None,
    #     app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/app_private_key.pem"),
    #     alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/alipay_public_key.pem"),
    #     sign_type='RSA2',
    #     debug=True
    # )
    #
    # order_info = alipay.api_alipay_trade_page_pay(
    #     out_trade_no=gen_order_id(houseid),
    #     total_amount=str(1),
    #     subject=f'租房预定_{houseid}',
    #     return_url='http://120.77.222.217:8000/static/html/pay_success.html',
    # )
    #
    # full_payment_url = f'{settings.ALIPAY_URL}?{order_info}'
    #
    # return DefaultResponse(data={'url': full_payment_url})


@api_view(('POST', ))
def upload_house_photo(request):
    file_obj = request.FILES.get('mainphoto')
    if file_obj and len(file_obj) < MAX_PHOTO_SIZE:
        prefix = to_md5_hex(file_obj.file)
        filename = f'{prefix}{os.path.splitext(file_obj.name)[1]}'
        upload_stream_to_qiniu.delay(file_obj, filename, len(file_obj))
        photo = HousePhoto()
        photo.path = f'http://q69nr46pe.bkt.clouddn.com/{filename}'
        photo.ismain = True
        photo.save()
        resp = DefaultResponse(*FILE_UPLOAD_SUCCESS, data={
            'photoid': photo.photoid,
            'url': photo.path
        })
    else:
        resp = DefaultResponse(*FILE_SIZE_EXCEEDED)
    return resp


@api_view(('GET', ))
def get_code_by_sms(request, tel):
    """获取短信验证码"""
    if check_tel(tel):
        if caches['default'].get(f'{tel}:block'):
            resp = DefaultResponse(*CODE_TOO_FREQUENCY)
        else:
            code = gen_mobile_code()
            message = f'您的短信验证码是{code}，打死也不能告诉别人哟！【Python小课】'
            send_sms_by_luosimao.apply_async((tel, message),
                                             countdown=random.random() * 5)
            caches['default'].set(f'{tel}:block', code, timeout=120)
            caches['default'].set(f'{tel}:valid', code, timeout=1800)
            resp = DefaultResponse(*MOBILE_CODE_SUCCESS)
    else:
        resp = DefaultResponse(*INVALID_TEL_NUM)
    return resp


@api_view(('POST', ))
def login(request):
    """登录（获取用户身份令牌）"""
    username = request.data.get('username')
    password = request.data.get('password')
    if (check_username(username) or check_tel(username) or
            check_email(username)) and len(password) >= 6:
        password = to_md5_hex(password)
        q = Q(username=username, password=password) | \
            Q(tel=username, password=password) | \
            Q(email=username, password=password)
        user = User.objects.filter(q)\
            .only('username', 'realname').first()
        if user:
            # 用户登录成功通过JWT生成用户身份令牌
            payload = {
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
                'data': {
                    'userid': user.userid,
                }
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode()
            with atomic():
                current_time = timezone.now()
                if not user.lastvisit or \
                        (current_time - user.lastvisit).days >= 1:
                    user.point += 2
                    user.lastvisit = current_time
                    user.save()
                loginlog = LoginLog()
                loginlog.user = user
                loginlog.logdate = current_time
                loginlog.ipaddr = get_ip_address(request)
                loginlog.save()
            resp = DefaultResponse(*USER_LOGIN_SUCCESS, data={
                'token': token, 'username': user.username, 'realname': user.realname
            })
        else:
            resp = DefaultResponse(*USER_LOGIN_FAILED)
    else:
        resp = DefaultResponse(*INVALID_LOGIN_INFO)
    return resp


@api_view(('DELETE', ))
def logout(request):
    """注销（销毁用户身份令牌）"""
    # 如果使用了JWT这种方式通过令牌进行用户身份认证
    # 如何彻底让令牌失效??? ---> Redis用集合类型做一个失效令牌清单
    # 定时任务从失效令牌清单中清理过期令牌避免集合元素过多
    pass


@cache_page(timeout=365 * 86400)
@api_view(('GET', ))
def get_provinces(request):
    """获取省级行政单位"""
    queryset = District.objects.filter(parent__isnull=True)\
        .only('name')
    serializer = DistrictSimpleSerializer(queryset, many=True)
    return Response({
        'code': 10000,
        'message': '获取省级行政区域成功',
        'results': serializer.data
    })


@api_view(('GET', ))
def get_district(request, distid):
    """获取地区详情"""
    redis_cli = get_redis_connection()
    data = redis_cli.get(f'zufang:district:{distid}')
    if data:
        data = ujson.loads(data)
    else:
        district = District.objects.filter(distid=distid)\
            .defer('parent').first()
        data = DistrictDetailSerializer(district).data
        redis_cli.set(f'zufang:district:{distid}', ujson.dumps(data), ex=900)
    return Response(data)


@method_decorator(decorator=cache_page(timeout=86400), name='get')
class HotCityView(ListAPIView):
    """热门城市视图
    get:
        获取热门城市
    """
    queryset = District.objects.filter(ishot=True).only('name')
    serializer_class = DistrictSimpleSerializer
    pagination_class = None


@method_decorator(decorator=cache_page(timeout=120), name='list')
@method_decorator(decorator=cache_page(timeout=300), name='retrieve')
class AgentViewSet(ModelViewSet):
    """经理人视图
    list:
        获取经理人列表
    retrieve:
        获取经理人详情
    create:
        创建经理人
    update:
        更新经理人信息
    partial_update:
        更新经理人信息
    delete:
        删除经理人
    """
    queryset = Agent.objects.all()

    def get_queryset(self):
        name = self.request.GET.get('name')
        if name:
            self.queryset = self.queryset.filter(name__startswith=name)
        servstar = self.request.GET.get('servstar')
        if servstar:
            self.queryset = self.queryset.filter(servstar__gte=servstar)
        if self.action == 'list':
            self.queryset = self.queryset.only('name', 'tel', 'servstar')
        else:
            self.queryset = self.queryset.prefetch_related(
                Prefetch('estates',
                         queryset=Estate.objects.all().only('name').order_by('-hot'))
            )
        return self.queryset.order_by('-servstar')

    def get_serializer_class(self):
        if self.action in ('create', 'update'):
            return AgentCreateSerializer
        return AgentDetailSerializer if self.action == 'retrieve' \
            else AgentSimpleSerializer


@method_decorator(decorator=cache_page(timeout=86400), name='list')
@method_decorator(decorator=cache_page(timeout=86400), name='retrieve')
class HouseTypeViewSet(ModelViewSet):
    """户型视图集"""
    queryset = HouseType.objects.all()
    serializer_class = HouseTypeSerializer
    pagination_class = None


@method_decorator(decorator=cache_page(timeout=3600), name='list')
class TagViewSet(ModelViewSet):
    """房源标签视图集"""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


@method_decorator(decorator=cache_page(timeout=300), name='list')
@method_decorator(decorator=cache_page(timeout=300), name='retrieve')
class EstateViewSet(ModelViewSet):
    """楼盘视图集"""
    queryset = Estate.objects.all()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = EstateFilterSet
    ordering = '-hot'
    ordering_fields = ('district', 'hot', 'name')
    authentication_classes = (LoginRequiredAuthentication, )
    permission_classes = (RbacPermission, )

    def get_queryset(self):
        if self.action == 'list':
            queryset = self.queryset.only('name')
        else:
            queryset = self.queryset\
                .defer('district__parent', 'district__ishot', 'district__intro')\
                .select_related('district')
        return queryset

    def get_serializer_class(self):
        if self.action in ('create', 'update'):
            return EstateCreateSerializer
        return EstateDetailSerializer if self.action == 'retrieve' \
            else EstateSimpleSerializer


@method_decorator(decorator=cache_page(timeout=120), name='list')
@method_decorator(decorator=cache_page(timeout=300), name='retrieve')
class HouseInfoViewSet(ModelViewSet):
    """房源视图集"""
    queryset = HouseInfo.objects.all()
    serializer_class = HouseInfoDetailSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = HouseInfoFilterSet
    ordering = ('-pubdate', )
    ordering_fields = ('pubdate', 'price')

    @action(methods=('GET', ), detail=True)
    def photos(self, request, pk):
        queryset = HousePhoto.objects.filter(house=self.get_object())
        return Response(HousePhotoSerializer(queryset, many=True).data)

    def get_queryset(self):
        if self.action == 'list':
            return self.queryset\
                .only('houseid', 'title', 'area', 'floor', 'totalfloor', 'price',
                      'mainphoto', 'priceunit', 'street', 'type',
                      'district_level3__distid', 'district_level3__name')\
                .select_related('district_level3', 'type')\
                .prefetch_related('tags')
        return self.queryset\
            .defer('user', 'district_level2',
                   'district_level3__parent', 'district_level3__ishot', 'district_level3__intro',
                   'estate__district', 'estate__hot', 'estate__intro',
                   'agent__realstar', 'agent__profstar', 'agent__certificated')\
            .select_related('district_level3', 'type', 'estate', 'agent')\
            .prefetch_related('tags')

    def get_serializer_class(self):
        if self.action in ('create', 'update'):
            return HouseInfoCreateSerializer
        return HouseInfoDetailSerializer if self.action == 'retrieve' \
            else HouseInfoSimpleSerializer


class UserViewSet(ModelViewSet):
    """用户模型视图集"""
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'update':
            return UserUpdateSerializer
        return UserSimpleSerializer
