import ujson
from django.core.cache import caches
from django.db.models import Q
from django.db.transaction import atomic

from django_redis import get_redis_connection
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from common.models import District, Agent, Estate, HouseType, Tag, \
    HouseInfo, HousePhoto, User, Role, UserRole
from common.utils import to_md5_hex
from common.validators import *


class DistrictSimpleSerializer(serializers.ModelSerializer):
    """地区简单序列化器"""

    class Meta:
        model = District
        fields = ('distid', 'name')


class DistrictDetailSerializer(serializers.ModelSerializer):
    """地区详情序列化器"""
    cities = serializers.SerializerMethodField()

    @staticmethod
    def get_cities(district):
        redis_cli = get_redis_connection()
        data = redis_cli.get(f'zufang:district:{district.distid}:cities')
        if data:
            data = ujson.loads(data)
        else:
            queryset = District.objects.filter(parent=district).only('name')
            data = DistrictSimpleSerializer(queryset, many=True).data
            redis_cli.set(f'zufang:district:{district.distid}:cities',
                          ujson.dumps(data), ex=900)
        return data

    class Meta:
        model = District
        exclude = ('parent', )


class AgentSimpleSerializer(serializers.ModelSerializer):
    """经理人简单序列化器"""

    class Meta:
        model = Agent
        fields = ('agentid', 'name', 'tel', 'servstar')


class AgentCreateSerializer(serializers.ModelSerializer):
    """创建经理人序列化器"""

    class Meta:
        model = Agent
        exclude = ('estates', )


class AgentDetailSerializer(serializers.ModelSerializer):
    """经理人详情序列化器"""
    estates = serializers.SerializerMethodField()

    @staticmethod
    def get_estates(agent):
        queryset = agent.estates.all()[:5]
        return EstateSimpleSerializer(queryset, many=True).data

    class Meta:
        model = Agent
        fields = '__all__'


class EstateSimpleSerializer(serializers.ModelSerializer):
    """楼盘简单序列化器"""

    class Meta:
        model = Estate
        fields = ('estateid', 'name')


class EstateCreateSerializer(serializers.ModelSerializer):
    """创建楼盘序列化器"""

    class Meta:
        model = Estate
        fields = '__all__'


class EstateDetailSerializer(serializers.ModelSerializer):
    """楼盘详情序列化器"""
    district = DistrictSimpleSerializer()

    class Meta:
        model = Estate
        fields = '__all__'


class HouseTypeSerializer(serializers.ModelSerializer):
    """户型序列化器"""

    class Meta:
        model = HouseType
        fields = '__all__'


class TagSerializer(serializers.ModelSerializer):
    """房源标签序列化器"""

    class Meta:
        model = Tag
        fields = '__all__'


class HouseInfoSimpleSerializer(serializers.ModelSerializer):
    """房源基本信息序列化器"""
    mainphoto = serializers.SerializerMethodField()
    district = serializers.SerializerMethodField()
    type = HouseTypeSerializer()
    tags = TagSerializer(many=True)

    @staticmethod
    def get_mainphoto(houseinfo):
        return '/media/images/' + houseinfo.mainphoto

    @staticmethod
    def get_district(houseinfo):
        return DistrictSimpleSerializer(houseinfo.district_level3).data

    class Meta:
        model = HouseInfo
        fields = ('houseid', 'title', 'area', 'floor', 'totalfloor',
                  'price', 'priceunit', 'mainphoto', 'street',
                  'district', 'type', 'tags')


class HouseInfoCreateSerializer(serializers.ModelSerializer):
    """创建房源序列化器"""

    class Meta:
        model = HouseInfo
        fields = '__all__'


class HouseInfoDetailSerializer(serializers.ModelSerializer):
    """房源详情序列化器"""
    photos = serializers.SerializerMethodField()
    district = serializers.SerializerMethodField()
    type = HouseTypeSerializer()
    agent = AgentSimpleSerializer()
    estate = EstateSimpleSerializer()
    tags = TagSerializer(many=True)

    @staticmethod
    def get_photos(houseinfo):
        queryset = HousePhoto.objects.filter(house=houseinfo)
        return HousePhotoSerializer(queryset, many=True).data

    @staticmethod
    def get_district(houseinfo):
        return DistrictSimpleSerializer(houseinfo.district_level3).data

    class Meta:
        model = HouseInfo
        exclude = ('district_level2', 'district_level3', 'user')


class HousePhotoSerializer(serializers.ModelSerializer):
    """房源照片序列化器"""

    class Meta:
        model = HousePhoto
        fields = ('photoid', 'path')


class UserSimpleSerializer(serializers.ModelSerializer):
    """用户简单序列化器"""

    class Meta:
        model = User
        exclude = ('password', 'roles')


class UserUpdateSerializer(serializers.ModelSerializer):
    """更新用户序列化器"""

    class Meta:
        model = User
        fields = ('realname', 'tel', 'email', 'sex')


class UserCreateSerializer(serializers.ModelSerializer):
    """创建用户序列化器"""
    username = serializers.RegexField(regex=USERNAME_PATTERN)
    password = serializers.CharField(min_length=6)
    realname = serializers.RegexField(regex=r'[\u4e00-\u9fa5]{2,20}')
    tel = serializers.RegexField(regex=TEL_PATTERN)
    email = serializers.RegexField(regex=EMAIL_PATTERN)
    code = serializers.CharField(write_only=True, min_length=6, max_length=6)

    def validate(self, attrs):
        code_from_user = attrs['code']
        code_from_redis = caches['default'].get(f'{attrs["tel"]}:valid')
        if code_from_redis != code_from_user:
            raise ValidationError('请输入有效的手机验证码', 'invalid')
        user = User.objects.filter(Q(username=attrs['username']) |
                                   Q(tel=attrs['tel']) |
                                   Q(email=attrs['email']))
        if user:
            raise ValidationError('用户名、手机或邮箱已被注册', 'invalid')
        return attrs

    def create(self, validated_data):
        del validated_data['code']
        caches['default'].delete(f'{validated_data["tel"]}:valid')
        validated_data['password'] = to_md5_hex(validated_data['password'])
        with atomic():
            user = User.objects.create(**validated_data)
            role = Role.objects.get(roleid=1)
            UserRole.objects.create(user=user, role=role)
        return user

    class Meta:
        model = User
        exclude = ('userid', 'regdate', 'point', 'lastvisit', 'roles')


class RoleSimpleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = ('roleid', )
