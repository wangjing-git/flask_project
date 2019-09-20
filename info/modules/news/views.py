from flask import render_template, g, current_app, abort, jsonify, request

from info import constants, db
from info.models import News, Category, Comment, CommentLike, User
from info.modules.news import news_blu
from info.response_code import RET
from info.utils.common import user_login_data


@news_blu.route('/<int:news_id>')
@user_login_data
def news_detail(news_id):
    user = g.user
    click_news = []
    # 查询新闻数据
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        abort(404)
    # 校验报404错误
    # if not news:
    #     abort(404)
    categorys = Category.query.all()
    if not categorys:
        return jsonify(errno=RET.DBERR,errmsg='新闻数据更新失败')
    # 进入详情页后要更新新闻的点击次数
    news.clicks += 1
    try:
        click_news = News.query.order_by(News.content.desc()).limit(constants.CLICK_RANK_MAX_NEWS).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='新闻数据查询错误')
    # 获取当前新闻最新的评论,并按时间排序
    comments = Comment.query.filter(Comment.news_id == news.id).order_by(Comment.create_time.desc()).all()
    # print(comments)
    if user:
        comment_like_ids = [commentlike.comment_id for commentlike in
                            CommentLike.query.filter(CommentLike.user_id == user.id).all()]
    else:
        comment_like_ids =[]
    # 遍历评论id,将评论属性赋值
    comment_dict_list = []
    for comment in comments:
        comment_dict = comment.to_dict()
        # 为评论增加'is_like'字段,判断是否评论
        comment_dict['is_like'] = False
        # 判断用户是否在点赞评论里
        if comment.id in comment_like_ids:
                comment_dict["is_like"] = True
        comment_dict_list.append(comment_dict)
    # 判断是否收藏该新闻，默认值为 false
    is_collected = False
    # 判断用户是否收藏过该新闻
    if user:
        if news in user.collection_news:
            is_collected = True
        # 当前登录用户是否关注当前新闻作者
    is_followed = False
    # 判断用户是否收藏过该新闻
    if news.user and user:
        if news.user in user.followed:
            is_followed = True
    # 返回数据
    data = {
        # "user": g.user.to_dict() if g.user else None,
        "user": user.to_dict() if user else None,
        'news': news.to_dict(),
        'news_dict': click_news,
        'is_collected': is_collected,
        'comments': comment_dict_list,
        'is_followed': is_followed
    }
    return render_template('news/detail.html', data=data)


@news_blu.route("/news_collect", methods=['POST'])
@user_login_data
def news_collect():
    """新闻收藏"""

    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg='用户未登录')
    # 获取参数
    news_id = request.json.get('news_id')    # 新闻id
    action = request.json.get('action')     # 指定两个值：'collect'收藏, 'cancel_collect'取消收藏
    # 判断参数
    try:
        news_id = int(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg='新闻收藏参数获取失败')
    # action在不在指定的两个值：'collect', 'cancel_collect'内
    if action not in ['collect', 'cancel_collect']:
        return jsonify(errno=RET.PARAMERR,errmsg='新闻收藏参数错误')
    # 查询新闻,并判断新闻是否存在
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询新闻失败')
        # 收藏/取消收藏
    if action == "cancel_collect":
        # 取消收藏
        if news in user.collection_news:
            user.collection_news.remove(news)
            return jsonify(errno=RET.OK, errmsg='取消收藏成功')
        else:
            return jsonify(errno=RET.DBERR,errmsg='取消收藏失败')
    else:
        # 收藏
        if news not in user.collection_news:
            user.collection_news.append(news)
            return jsonify(errno=RET.OK, errmsg='收藏成功')
    # 返回
    return jsonify(errno=RET.OK, errmsg='收藏成功')


@news_blu.route('/news_comment', methods=["POST"])
@user_login_data
def add_news_comment():
    """添加评论"""

    # 用户是否登陆
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg='评论用户未登录')
    # 获取参数
    content = request.json.get('comment')    # 评论内容
    parent_id = request.json.get('parent_id')    # 回复的评论的id
    news_id = request.json.get('news_id')    # 新闻id
    if not all([content, news_id]):
        return jsonify(errno=RET.PARAMERR, errmsg='新闻评论参数错误')
    # 判断参数是否正确
    news_id = int(news_id)
    if parent_id:
        parent_id = int(parent_id)
    # 查询新闻是否存在并校验
    news = News.query.get(news_id)
    if not news:
        return jsonify(errno=RET.DBERR, errmsg='查询新闻失败')
    # print(1234)
    # 初始化评论模型，保存数据
    comment = Comment()
    comment.user_id = user.id
    comment.news_id = news_id
    comment.content = content
    # 配置文件设置了自动提交,自动提交要在return返回结果以后才执行commit命令,如果有回复
    if parent_id:
        comment.parent_id = parent_id
    # 评论,先拿到回复评论id,在手动commit,否则无法获取回复评论内容
    try:
        db.session.add(comment)
        db.session.commit()
        # return jsonify(errno=RET.OK, errmsg='评论成功')
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        # return jsonify(errno=RET.DBERR, errmsg='评论添加失败')
    return jsonify(errno=RET.OK, errmsg='评论成功',data=comment.to_dict())


@news_blu.route('/comment_like', methods=["POST"])
@user_login_data
def comment_like():
    """
    评论点赞
    :return:
    """
    # 用户是否登陆
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR,errmsg='评论点赞用户未登录')
    # 取到请求参数
    comment_id = request.json.get('comment_id')    # 评论id
    action = request.json.get('action')    # 点赞操作类型：add(点赞)，remove(取消点赞)
    # 判断参数
    if not all([comment_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg='评论点赞参数错误')
    try:
        comment_id = int(comment_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg='评论编号参数错误')
    # 获取到要被点赞的评论模型
    if action not in ['add', 'remove']:
        return jsonify(errno=RET.PARAMERR,errmsg='评论点赞参数错误')
    comments = Comment.query.get(comment_id)
    if not comments:
        return jsonify(errno=RET.DBERR, errmsg='查询不存在')
    # 查询到用户新闻点赞状态
    comment_like = CommentLike.query.filter(CommentLike.user_id == user.id, CommentLike.comment_id == comments.id).first()
    # action的状态,如果点赞,则查询后将用户id和评论id添加到数据库
            # 点赞评论
            # 更新点赞次数
    if not comment_like:
        comment_like = CommentLike()
        comment_like.user_id = user.id
        comment_like.comment_id = comments.id
        db.session.add(comment_like)
        comments.like_count += 1
        # db.session.commit()
        return jsonify(errno=RET.OK, errmsg='评论点赞成功')
        # 取消点赞评论,查询数据库,如果以点在,则删除点赞信息
        # 更新点赞次数
    else:
        db.session.delete(comment_like)
        comments.like_count -= 1
        # db.session.commit()
        return jsonify(errno=RET.OK, errmsg='取消点赞成功')
    # 返回结果


@news_blu.route('/followed_user', methods=["POST"])
@user_login_data
def followed_user():
    """关注或者取消关注用户"""

    # 获取自己登录信息
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="未登录")

    # 获取参数
    user_id = request.json.get("user_id")    # 被关注的用户id
    action = request.json.get("action")    # 指定两个值：'follow', 'unfollow'

    # 判断参数
    if not all([user_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if action not in ("follow", "unfollow"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 获取要被关注的用户
    try:
        other = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询错误")

    if not other:
        return jsonify(errno=RET.NODATA, errmsg="未查询到数据")

    if other.id == user.id:
        return jsonify(errno=RET.PARAMERR, errmsg="请勿关注自己")

    # 根据要执行的操作去修改对应的数据
    if action == "follow":
        if other not in user.followed:
            # 当前用户的关注列表添加一个值
            user.followed.append(other)
        else:
            return jsonify(errno=RET.DATAEXIST, errmsg="当前用户已被关注")
    else:
        # 取消关注
        if other in user.followed:
            user.followed.remove(other)
        else:
            return jsonify(errno=RET.DATAEXIST, errmsg="当前用户未被关注")

    return jsonify(errno=RET.OK, errmsg="操作成功")

