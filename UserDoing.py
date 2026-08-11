import requests
import sys
import time
import os

# ===================== 全局配置区（可按需调整） =====================
# 接口地址（无需修改，与文档完全匹配）
SUBMIT_TASK_URL = "https://api.wuyinkeji.com/api/async/image_gpt"
GET_RESULT_URL = "https://api.wuyinkeji.com/api/async/detail"

# 轮询配置（生成耗时较长可调整）
MAX_POLL_TIMES = 60       # 最大轮询次数
POLL_INTERVAL = 2         # 每次轮询间隔（秒）
REQUEST_TIMEOUT = 30      # 单次请求超时时间（秒）

# 全局参数存储（无需手动修改，通过命令交互设置）
API_KEY = ""
PROMPT = ""
SIZE = "auto"
REFERENCE_URLS = []
# ====================================================================


def load_key_from_txt():
    """
    自动读取同目录下的key.txt文件，设置API_KEY
    :return: 成功返回True，失败返回False
    """
    global API_KEY
    # 获取同目录下key.txt的绝对路径
    key_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.txt")
    
    # 检查文件是否存在
    if not os.path.exists(key_file_path):
        print(f"💡 提示：同目录下未找到 key.txt 文件，可手动使用 key 命令设置")
        return False
    
    try:
        # 读取文件内容
        with open(key_file_path, "r", encoding="utf-8") as f:
            file_content = f.read().strip()
        
        # 校验内容是否为空
        if not file_content:
            print(f"⚠️  警告：key.txt 文件内容为空，请检查后重试，或手动使用 key 命令设置")
            return False
        
        # 设置API_KEY
        API_KEY = file_content
        print(f"✅ 已自动从 key.txt 读取API密钥，当前密钥：{API_KEY[:4]}****{API_KEY[-4:]}")
        return True

    except Exception as e:
        print(f"❌ 读取 key.txt 文件失败：{str(e)}")
        print(f"💡 请检查文件是否存在、是否有读取权限，或手动使用 key 命令设置")
        return False


def save_task_id_to_txt(task_id: str):
    """
    将任务ID追加保存到同目录下的id.txt文件中
    :param task_id: 要保存的任务ID
    :return: 成功返回True，失败返回False
    """
    id_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "id.txt")
    
    try:
        # 以追加模式打开文件，写入任务ID并换行
        with open(id_file_path, "a", encoding="utf-8") as f:
            f.write(task_id + "\n")
        print(f"✅ 任务ID已自动保存到 id.txt")
        return True
    except Exception as e:
        print(f"❌ 保存任务ID到 id.txt 失败：{str(e)}")
        return False


def print_help():
    """程序启动时打印命令&功能对照表"""
    help_content = """
=====================================
  图像生成API 命令行交互工具
=====================================
命令 & 功能对照表：
help      查看命令帮助说明
key       手动设置接口密钥（API_KEY）
prompt    设置生成提示词（支持多行输入）
ratio     设置生成图片的宽高比例
reference 设置参考图URL链接
get       提交生成任务并获取结果
list_id   查看同目录下 id.txt 中的所有任务ID
query_id  查询指定任务ID的结果，输出图片地址
exit      退出当前程序
=====================================
💡 提示：程序启动时会自动读取同目录下的 key.txt 文件
    """
    print(help_content)


def handle_key():
    """处理key命令：设置API密钥"""
    global API_KEY
    print("请输入key：")
    try:
        input_key = input().strip()
        if not input_key:
            print("❌ 错误：key不能为空，请重新输入")
            return
        API_KEY = input_key
        print(f"✅ API密钥设置成功，当前密钥：{API_KEY[:4]}****{API_KEY[-4:]}")
    except Exception as e:
        print(f"❌ 输入异常：{str(e)}")


def handle_prompt():
    """处理prompt命令：支持多行输入，回车换行，Ctrl+Z回车确认"""
    global PROMPT
    print("请输入提示词，按【回车/Shift+回车】换行，输入完成后按【Ctrl+Z 回车】确认：")
    try:
        # 读取多行输入，直到用户输入EOF结束
        input_prompt = sys.stdin.read().strip()
        if not input_prompt:
            print("❌ 错误：提示词不能为空，请重新输入")
            return
        PROMPT = input_prompt
        print(f"✅ 提示词设置成功，当前提示词长度：{len(PROMPT)} 字符")
        # 打印预览，避免过长内容刷屏
        preview = PROMPT[:100] + "..." if len(PROMPT) > 100 else PROMPT
        print(f"提示词预览：{preview}")
    except Exception as e:
        print(f"❌ 输入异常：{str(e)}")


def handle_ratio():
    """处理ratio命令：设置图片宽高比例"""
    global SIZE
    print("请输入图片比例（可选值：auto、1:1、3:2、2:3、16:9、9:16、4:3、3:4、21:9、9:21、1:3、3:1、2:1、1:2）：")
    try:
        input_ratio = input().strip()
        if not input_ratio:
            print("❌ 错误：比例不能为空，请重新输入")
            return
        SIZE = input_ratio
        print(f"✅ 图片比例设置成功，当前比例：{SIZE}")
    except Exception as e:
        print(f"❌ 输入异常：{str(e)}")


def handle_reference():
    """处理reference命令：设置参考图URL，支持多个"""
    global REFERENCE_URLS
    print("请输入参考图URL（多个URL用英文逗号分隔，无参考图直接回车清空）：")
    try:
        input_urls = input().strip()
        if not input_urls:
            REFERENCE_URLS = []
            print("✅ 参考图链接已清空")
            return
        # 分割、去重、过滤空值
        url_list = [url.strip() for url in input_urls.split(",") if url.strip()]
        REFERENCE_URLS = url_list
        print(f"✅ 参考图链接设置成功，共 {len(REFERENCE_URLS)} 个链接")
        for idx, url in enumerate(REFERENCE_URLS, 1):
            print(f"  {idx}. {url}")
    except Exception as e:
        print(f"❌ 输入异常：{str(e)}")


def handle_list_id():
    """处理list_id命令：打印同目录下id.txt中的所有任务ID"""
    id_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "id.txt")
    
    # 检查文件是否存在
    if not os.path.exists(id_file_path):
        print(f"💡 提示：同目录下未找到 id.txt 文件，尚未提交过生成任务")
        return
    
    try:
        # 读取文件内容
        with open(id_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 过滤空行，去除每行末尾的换行符
        task_ids = [line.strip() for line in lines if line.strip()]
        
        if not task_ids:
            print(f"💡 提示：id.txt 文件为空，尚未保存过任务ID")
            return
        
        # 打印所有任务ID
        print(f"\n==================== id.txt 中的任务ID ====================")
        for idx, task_id in enumerate(task_ids, 1):
            print(f"  {idx}. {task_id}")
        print("=============================================================")
        
    except Exception as e:
        print(f"❌ 读取 id.txt 文件失败：{str(e)}")


def query_task_result(task_id: str):
    """单次查询任务结果，返回完整响应数据，失败返回None"""
    if not API_KEY or not task_id:
        print("❌ 错误：API密钥或任务ID为空")
        return None

    query_params = {
        "key": API_KEY,
        "id": task_id
    }

    try:
        response = requests.get(
            url=GET_RESULT_URL,
            params=query_params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 任务查询异常：{str(e)}")
        return None


def handle_query_id():
    """处理query_id命令：查询指定任务ID的结果，输出result字段（图片地址）"""
    # 前置校验
    if not API_KEY:
        print("❌ 错误：未设置API密钥，请先使用 key 命令设置，或在同目录下创建 key.txt 文件")
        return
    
    # 获取用户输入的任务ID
    print("请输入要查询的任务ID：")
    try:
        task_id = input().strip()
        if not task_id:
            print("❌ 错误：任务ID不能为空，请重新输入")
            return
    except Exception as e:
        print(f"❌ 输入异常：{str(e)}")
        return
    
    # 调用查询接口
    print(f"正在查询任务ID：{task_id} ...")
    result = query_task_result(task_id)
    
    # 处理查询结果
    if not result:
        return
    
    # 校验接口业务状态
    if result.get("code") != 200:
        print(f"❌ 查询失败，状态码：{result.get('code')}，错误信息：{result.get('msg')}")
        return
    
    # 提取并打印result字段
    task_data = result.get("data", {})
    result_content = task_data.get("result", [])
    
    print(f"✅ 任务查询成功！")
    print(f"\n==================== 任务result字段内容 ====================")
    if not result_content:
        print("⚠️  result字段为空，暂无生成的图片地址")
    else:
        for idx, url in enumerate(result_content, 1):
            print(f"  第{idx}张图片地址：{url}")
    print("=============================================================")


def submit_generate_task():
    """提交图像生成任务，返回任务ID，失败返回None"""
    # 前置参数校验
    if not API_KEY:
        print("❌ 错误：未设置API密钥，请先使用 key 命令设置，或在同目录下创建 key.txt 文件")
        return None
    if not PROMPT:
        print("❌ 错误：未设置提示词，请先使用 prompt 命令设置")
        return None

    # 构造请求参数（与文档完全匹配）
    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }
    url_params = {"key": API_KEY}
    request_body = {
        "prompt": PROMPT,
        "size": SIZE,
        "urls": REFERENCE_URLS
    }

    try:
        print("正在提交生成任务...")
        response = requests.post(
            url=SUBMIT_TASK_URL,
            params=url_params,
            headers=headers,
            json=request_body,
            timeout=REQUEST_TIMEOUT
        )
        # 校验HTTP状态
        response.raise_for_status()
        result = response.json()

        # 校验接口业务状态
        if result.get("code") == 200:
            task_id = result.get("data", {}).get("id")
            print(f"✅ 任务提交成功，任务ID：{task_id}")
            # 自动保存任务ID到id.txt
            save_task_id_to_txt(task_id)
            return task_id
        else:
            print(f"❌ 任务提交失败，状态码：{result.get('code')}，错误信息：{result.get('msg')}")
            return None

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP请求错误：{str(e)}")
        if 'response' in locals():
            print(f"响应原始内容：{response.text}")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ 网络连接错误，请检查网络是否正常、接口地址是否可访问")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时，超过{REQUEST_TIMEOUT}秒未收到响应")
        return None
    except Exception as e:
        print(f"❌ 任务提交发生未知异常：{str(e)}")
        return None


def poll_task_until_complete(task_id: str):
    """轮询等待任务完成，返回最终结果，失败/超时返回None"""
    print(f"\n开始轮询任务结果，最长等待时间：{MAX_POLL_TIMES * POLL_INTERVAL} 秒")
    for retry_count in range(MAX_POLL_TIMES):
        print(f"\n第 {retry_count+1}/{MAX_POLL_TIMES} 次查询...")
        result = query_task_result(task_id)

        # 查询异常，跳过本次，继续轮询
        if not result:
            time.sleep(POLL_INTERVAL)
            continue

        # 接口业务报错，终止轮询
        if result.get("code") != 200:
            print(f"❌ 任务查询失败，状态码：{result.get('code')}，信息：{result.get('msg')}")
            return None

        task_data = result.get("data", {})
        task_status = task_data.get("status", 1)

        # 状态判断（与你提供的返回结果完全匹配：status=2=成功，1=生成中，其他=失败）
        if task_status == 2:
            print("🎉 图片生成完成！")
            print(f"完整返回结果：{result}")
            return result
        elif task_status == 1:
            print(f"⏳ 任务正在生成中，继续等待...")
            time.sleep(POLL_INTERVAL)
        else:
            print(f"❌ 任务生成失败，状态码：{task_status}，错误信息：{task_data.get('message', '未知错误')}")
            return result

    # 达到最大轮询次数仍未完成
    print(f"\n⚠️  已达到最大轮询次数，任务仍未完成，请手动查询或延长轮询时间")
    return None


def handle_get():
    """处理get命令：打印参数、用户确认、提交任务、获取结果"""
    # 前置参数校验
    if not API_KEY:
        print("❌ 错误：未设置API密钥，请先使用 key 命令设置，或在同目录下创建 key.txt 文件")
        return
    if not PROMPT:
        print("❌ 错误：未设置提示词，请先使用 prompt 命令设置")
        return

    # 打印当前所有调用参数
    print("\n==================== 当前调用参数 ====================")
    print(f"API密钥：{API_KEY[:4]}****{API_KEY[-4:]}")
    print(f"提示词：{PROMPT}")
    print(f"图片比例：{SIZE}")
    print(f"参考图链接：{REFERENCE_URLS if REFERENCE_URLS else '无'}")
    print("=======================================================")

    # 用户二次确认
    print("\n请确认是否提交生成任务？输入 y 确认，输入 n 取消")
    try:
        confirm = input().strip().lower()
        if confirm != "y":
            print("❌ 已取消调用")
            return
    except Exception as e:
        print(f"❌ 输入异常：{str(e)}")
        return

    # 1. 提交任务
    task_id = submit_generate_task()
    if not task_id:
        return

    # 2. 轮询等待生成完成
    poll_task_until_complete(task_id)


def main():
    """主程序入口：交互式循环"""
    # 启动时打印命令对照表
    print_help()
    # 自动读取同目录下的key.txt
    print("\n正在尝试自动读取同目录下的 key.txt 文件...")
    load_key_from_txt()
    # 持续监听用户输入
    while True:
        print("\n请输入命令（输入help查看帮助，exit退出）：")
        try:
            command = input().strip().lower()
        except KeyboardInterrupt:
            # 处理Ctrl+C退出
            print("\n\n程序已正常退出")
            sys.exit(0)
        except Exception as e:
            print(f"❌ 输入异常：{str(e)}")
            continue

        # 命令分发
        if command == "help":
            print_help()
        elif command == "key":
            handle_key()
        elif command == "prompt":
            handle_prompt()
        elif command == "ratio":
            handle_ratio()
        elif command == "reference":
            handle_reference()
        elif command == "get":
            handle_get()
        elif command == "list_id":
            handle_list_id()
        elif command == "query_id":
            handle_query_id()
        elif command == "exit":
            print("程序已正常退出")
            sys.exit(0)
        else:
            print("❌ 未知命令，请输入help查看支持的命令列表")


if __name__ == "__main__":
    main()