import random
import re

from flask import request, abort, render_template, jsonify, make_response, current_app, session
from sqlalchemy.sql.functions import user

from info import db, redis_store, constants
from info.utils.captcha.captcha import captcha
from info.models import User
from info.response_code import RET
from info.utils.yuntongxun.sms import CCP
from . import passport_blu


@passport_blu.route('/image_code')
def get_image_code():
    '''
    生成图片验证码
    :return:
    '''
    # 1. 获取参数
    image_code = request.args.get('image_Code')
    # 2. 校验参数
    if not image_code:
        return abort(404)

    # 3. 生成图片验证码
    name, text, image = captcha.generate_captcha()
    print(text)
    # 4. 保存图片验证码，保存到redis中，变量名,值，时效，类型
    try:
        redis_store.setex('image_code' + image_code, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='图形验证保存失败')
    # 5.返回图片验证码
    response = make_response(image)
    response.content_type = 'image/jpg'
    return response


@passport_blu.route('/sms_code', methods=["POST"])
def send_sms_code():
    """
    发送短信的逻辑
    :return:
    """
    # 1.将前端参数转为字典
    mobile = request.json.get('mobile')   # 手机号
    # print(mobile)
    image_code = request.json.get('image_code')   # 用户输入的图片验证码内容
    image_code_id = request.json.get('image_code_id')  # 真实图片验证码编号
    # 2. 校验参数(参数是否符合规则，判断是否有值)
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 判断参数是否有值
    # match尝试从字符串的起始位置匹配，返回值是数组或者是null
    # 验证手机号的正则
    if not re.match(r'^1[3456789]\d{9}$', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='手机号格式错误')
    # 3. 先从redis中取出真实的图片验证码内容
    try:
        real_image_code = redis_store.get('image_code' + image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='图片验证码失误')
    if not real_image_code:
        return jsonify(errno=RET.DBERR, errmsg='图形有效期已过')
    # 4. 与用户的验证码内容进行对比，如果对比不一致，那么返回验证码输入错误
    if real_image_code != image_code:
        return jsonify(errno=RET.DATAERR,errmsg='图形验证码输入错误')
    # 5. 如果一致，生成短信验证码的内容(随机数据)
    sms_code_num = '%06d' % random.randint(0, 999999)
    print(sms_code_num)
    # 6. 发送短信验证码，云通讯辅助
    CCP().send_template_sms(mobile,[sms_code_num,constants.SMS_CODE_REDIS_EXPIRES / 5],"1")
    # if not result != 0:
    #     return jsonify(errno=RET.THIRDERR, errmsg='短信验证发送失败')
    # # 保存验证码内容到redis
    try:
        redis_store.set('sms_code_num' + mobile, sms_code_num,constants.SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='短信验证保存失败')
    # 7. 告知发送结果
    return jsonify(errno=RET.OK,errmsg='发送成功')


@passport_blu.route('/register', methods=["POST"])
def register():
    """
    注册功能
    :return:
    """
    # 1. 获取参数和判断是否有值
    # print('*' * 50)
    mobile = request.json.get('mobile')   # 手机号
    # print('*'*50)
    # print(mobile)
    smscode = request.json.get('smscode')   # 短信验证码
    password = request.json.get('password')   # 密码
    # print(mobile,smscode,password)
    if not all([mobile, smscode, password]):
        return jsonify(errno=RET.PARAMERR, errmsg='注册功能参数错误')
    if not re.match(r"1[35678]\d{9}$", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='号码错误')
    # 2. 从redis中获取指定手机号对应的短信验证码的
    try:
        real_smscode = redis_store.get('sms_code_num' + mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='获取失败')
    print(real_smscode)
    if not real_smscode:
        return jsonify(errno=RET.DBERR, errmsg='短信有效期已过')
    # 3. 校验验证码
    if real_smscode != smscode:
        return jsonify(errno=RET.DATAERR, errmsg='短信验证码输入错误')
    # 4. 初始化 user 模型，并设置数据并添加到数据库
    user = User()
    user.mobile = mobile
    user.nick_name = mobile
    user.password = password
    try:
        db.session.add(user)
        # db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='数据库添加失败')

    # 5. 保存用户登录状态
    session['user_id'] = user.id
    session['user_nick_name'] = user.nick_name
    # 6. 返回注册结果
    return jsonify(errno=RET.OK, errmsg='注册成功')


@passport_blu.route('/login', methods=["POST"])
def login():
    """
    登陆功能
    :return:
    """

    # 1. 获取参数和判断是否有值
    mobile = request.json.get('mobile')   # 手机号
    password = request.json.get('password')   # 密码
    if not all([mobile, password]):
        return jsonify(errno=RET.PARAMERR, errmsg='账户不存在')
    # 2. 从数据库查询出指定的用户
    user = User.query.filter(User.mobile == mobile).first()
    if not user:
        return jsonify(errno=RET.USERERR, errmsg='用户不存在')
    # 3. 校验密码 User中的一个方法check_password验证密码
    if not user.check_password(password):
        return jsonify(errno=RET.DBERR, errmsg='密码输入错误')
    # 4. 保存用户登录状态
    session['user_id'] = user.id
    # session['user_nick_name'] = user.nick_name
    # 5. 登录成功返回
    return jsonify(errno=RET.OK, errmsg='登录成功')


@passport_blu.route("/logout", methods=['POST'])
def logout():
    """
    清除session中的对应登录之后保存的信息
    :return:
    """
    # 返回结果
    session.pop('user_id')  # 清除session中的对应登录之后保存的信息
    return jsonify(errno=RET.OK, errmsg='退出登录成功')

