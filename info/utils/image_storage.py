from qiniu import Auth, put_data

access_key = 'Q3l0L4uo8vTXvLs6UacKg3xHykxxhoZSzmFIlf6w'
secret_key = 'r8Bn58sGxNz1jcD2HY8tbTEiZwecBOg1eZgDcIB3'
# 七牛云创建的储存空间名称
bucket_name = 'news_info'


def storage(data):
    try:
        q = Auth(access_key, secret_key)
        token = q.upload_token(bucket_name)
        ret, info = put_data(token, None, data)
        print(ret, info)
    except Exception as e:
        raise e

    if info.status_code != 200:
        raise Exception('上传图片失败')
    return ret['key']


if __name__ == '__main__':
    file = input('请输入路径')
    with open(file, 'rb') as f:
        storage(f.read())