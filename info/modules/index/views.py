from flask import render_template, session, current_app, abort, jsonify, request, g

from info import constants
from info.models import User, News, Category
from info.response_code import RET
from info.utils.common import user_login_data
from . import index_blu


@index_blu.route('/')
@user_login_data
def index():
    # 获取到当前登录用户的id
    # 从session中获取
    # user_id = session.get('user_id')
    # user = None
    # if user_id:
    #     try:
    #         user = User.query.get(user_id)
    #     except Exception as e:
    #         current_app.logger.error(e)
    # 使用g变量获取用户登陆信息
    user = g.user
    # 右侧新闻排行
    clicks_news = []
    # 按照点击量排序查询出点击最高的前10条新闻
    try:
        clicks_news = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS).all()
    except Exception as e:
        current_app.logger.error(e)
    # 将对象字典添加到列表中
    # 获取新闻分类数据
    # 定义列表保存分类数据
    # category_id = []
    try:
        category_id = Category.query.filter(Category.id).all()  # 分类id
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='新闻分类查询错误')
    # 拼接内容
    # 返回数据
    data = {'user': user if user else None,
            'news_dict': clicks_news,
            'categories': category_id}
    # 返回给前端查询结果
    return render_template('news/index.html', data=data)


@index_blu.route('/news_list')
def news_list():
    """
    获取首页新闻数据
    :return:
    """
    # 1. 获取参数,并指定默认为最新分类,第一页,一页显示10条数据
    page = request.args.get('page', 1)   # 页数，不传即获取第1页
    per_page = request.args.get('per_page',constants.HOME_PAGE_MAX_NEWS)  # 每页多少条数据，如果不传，默认10条
    cid = request.args.get('cid', 0)  # 分类id
    print(page, per_page, cid)
    # 校验
    if not all([page, per_page, cid]):
        return jsonify(errno=RET.PARAMERR, errmsg='新闻列表获取错误')
    # 整数化
    page = int(page)
    per_page = int(per_page)
    cid = int(cid)
    # 当前新闻状态
    filters = [News.status == 0]
    # 如果分类id不为1，那么添加分类id的过滤
    if cid != 1:
        filters.append(News.category_id == cid)
    # 3. 查询数据并分页，paginate一个方法
    try:
        paginate = News.query.filter(*filters).order_by(News.create_time.desc()).paginate(page, per_page, False)
        paginates = paginate.items
        news = [i.to_dict() for i in paginates]
        # 获取总页数
        total_page = paginate.pages
        # 当前页数
        current_page = paginate.page
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='新闻列表错误')
    # 2. 校验参数
	  # 默认选择最新数据分类
    # 3. 查询数据
    # 将模型对象列表转成字典列表
    data = {'total_page': total_page,
            'news_dict_list': news}
    #返回数据
    return jsonify(errno=RET.OK,errmsg='列表数据显示完成', currentPage= current_page, data = data)


