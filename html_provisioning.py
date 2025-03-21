import network
import usocket as socket
import utime
import machine
from machine import Pin
import json

# 配置参数
AP_SSID = "设备配网WiFi"
HOST_NAME = "MY_ESP32"
AP_IP = '192.168.4.1'
AP_NETMASK = '255.255.255.0'
WEB_PORT = 80
LED_PIN = 2

# 全局变量
wifi_ssid = ""
wifi_pass = ""
led = Pin(LED_PIN, Pin.OUT)
ap = network.WLAN(network.AP_IF)
sta = network.WLAN(network.STA_IF)
ap.active(True)
sta.active(True)
scan_results = []
web_socket = None

# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>登录页面</title>
  <style>
    #content,.login,.login-card a,.login-card h1,.login-help{text-align:center}body,html{margin:0;padding:0;width:100%;height:100%;display:table}#content{font-family:'Source Sans Pro',sans-serif;-webkit-background-size:cover;-moz-background-size:cover;-o-background-size:cover;background-size:cover;display:table-cell;vertical-align:middle}.login-card{padding:40px;width:274px;background-color:#F7F7F7;margin:0 auto 10px;border-radius:20px;box-shadow:8px 8px 15px rgba(0,0,0,.3);overflow:hidden}.login-card h1{font-weight:400;font-size:2.3em;color:#1383c6}.login-card h1 span{color:#f26721}.login-card img{width:70%;height:70%}.login-card input[type=submit]{width:100%;display:block;margin-bottom:10px;position:relative}.login-card input[type=text],input[type=password]{height:44px;font-size:16px;width:100%;margin-bottom:10px;-webkit-appearance:none;background:#fff;border:1px solid #d9d9d9;border-top:1px solid silver;padding:0 8px;box-sizing:border-box;-moz-box-sizing:border-box}.login-card input[type=text]:hover,input[type=password]:hover{border:1px solid #b9b9b9;border-top:1px solid #a0a0a0;-moz-box-shadow:inset 0 1px 2px rgba(0,0,0,.1);-webkit-box-shadow:inset 0 1px 2px rgba(0,0,0,.1);box-shadow:inset 0 1px 2px rgba(0,0,0,.1)}.login{font-size:14px;font-family:Arial,sans-serif;font-weight:700;height:36px;padding:0 8px}.login-submit{-webkit-appearance:none;-moz-appearance:none;appearance:none;border:0;color:#fff;text-shadow:0 1px rgba(0,0,0,.1);background-color:#4d90fe}.login-submit:disabled{opacity:.6}.login-submit:hover{border:0;text-shadow:0 1px rgba(0,0,0,.3);background-color:#357ae8}.login-card a{text-decoration:none;color:#666;font-weight:400;display:inline-block;opacity:.6;transition:opacity ease .5s}.login-card a:hover{opacity:1}.login-help{width:100%;font-size:12px}.list{list-style-type:none;padding:0}.list__item{margin:0 0 .7rem;padding:0}label{display:-webkit-box;display:-webkit-flex;display:-ms-flexbox;display:flex;-webkit-box-align:center;-webkit-align-items:center;-ms-flex-align:center;align-items:center;text-align:left;font-size:14px;}input[type=checkbox]{-webkit-box-flex:0;-webkit-flex:none;-ms-flex:none;flex:none;margin-right:10px;float:left}.error{font-size:14px;font-family:Arial,sans-serif;font-weight:700;height:25px;padding:0 8px;padding-top: 10px; -webkit-appearance:none;-moz-appearance:none;appearance:none;border:0;color:#fff;text-shadow:0 1px rgba(0,0,0,.1);background-color:#ff1215}@media screen and (max-width:450px){.login-card{width:70%!important}.login-card img{width:30%;height:30%}}
  </style>
</head>
<body style="background-color: #e5e9f2">
<div id="content">
  <form name='input' action='/configwifi' method='POST'>
    <div class="login-card">
      <h1>WiFi登录</h1>
      <input type="text" name="ssid" placeholder="请输入 WiFi 名称" id="auth_user" list="data-list"; style="border-radius: 10px">
      <datalist id="data-list">
        {SSID_OPTIONS}
      </datalist>
      <input type="password" name="password" placeholder="请输入 WiFi 密码" id="auth_pass"; style="border-radius: 10px">
      <div class="login-help">
        <ul class="list">
          <li class="list__item">
          </li>
        </ul>
      </div>
      <input type="submit" class="login login-submit" value="确 定 连 接" id="login"; disabled; style="border-radius: 15px">
    </div>
    <!-- 添加WiFi列表显示区域 -->
    <div id="wifi-list">
      <h2>扫描到的WiFi列表</h2>
      <ul>
        {SCAN_RESULTS}
      </ul>
    </div>
    <script>
      // 添加JavaScript代码，点击WiFi名称自动填入输入框
      document.querySelectorAll('#wifi-list ul li').forEach(function(item) {
        item.addEventListener('click', function() {
          document.getElementById('auth_user').value = this.textContent;
        });
      });
    </script>
  </form>
</div>
</body>
</html>
"""

def init_ap():
    ap.active(False)  # 确保先关闭 AP
    utime.sleep(1)
    ap.active(True)
    ap.config(essid=AP_SSID, authmode=network.AUTH_OPEN)
    ap.ifconfig((AP_IP, AP_NETMASK, AP_IP, AP_IP))
    print("AP模式已启动，IP:", ap.ifconfig()[0])

def scan_wifi():
    sta.active(True)
    scan = sta.scan()
    sta.active(False)
    results = []
    for ssid in scan:
        try:
            results.append(ssid[0].decode('utf-8'))
        except:
            results.append(ssid[0].decode('latin-1'))
    return results

def handle_request(client):
    global wifi_ssid, wifi_pass
    try:
        request = client.recv(1024).decode()
        if "POST /config" in request:
            # 提取POST数据
            params = request.split('\r\n\r\n')[1]
            
            # MicroPython 手动实现URL解码
            def unquote(s):
                import binascii
                parts = s.split('%')
                res = [parts[0]]
                for part in parts[1:]:
                    try:
                        code = part[:2]
                        res.append(binascii.unhexlify(code).decode())
                        res.append(part[2:])
                    except:
                        res.append('%' + part)
                return ''.join(res).replace('+', ' ')  # 正确处理空格
            
            post_data = {}
            for pair in params.split('&'):
                key, value = pair.split('=', 1)
                post_data[key] = unquote(value)  # 使用自定义解码函数
                
            wifi_ssid = post_data.get('ssid', '')
            wifi_pass = post_data.get('password', '')
            
            # 返回响应
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
            response += f"<h1>正在连接 {wifi_ssid}...</h1>"
            client.send(response)
            client.close()
            return True
        
        # 处理GET请求
        else:
            ssid_options = "".join(f"<option value='{ssid}'>{ssid}</option>" for ssid in scan_results)
            scan_results_html = "".join(f"<li>{ssid}</li>" for ssid in scan_results)  # 添加扫描结果到HTML
            html = HTML_TEMPLATE.replace("{SSID_OPTIONS}", ssid_options).replace("{SCAN_RESULTS}", scan_results_html)
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            client.send(response)
            client.close()
        return False
    except Exception as e:
        print("请求处理异常:", e)
        return False

def run_web_server():
    global web_socket
    try:
        web_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        web_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 添加端口重用选项
        web_socket.bind(('0.0.0.0', WEB_PORT))
        web_socket.listen(1)
        print("Web服务器已启动")

        while True:
            try:
                client, addr = web_socket.accept()
                print("客户端连接:", addr)
                if handle_request(client):
                    break
            except Exception as e:
                print("请求处理错误:", e)
            finally:
                client.close()
    except OSError as e:
        if e.args[0] == 112:  # 特定处理地址占用错误
            print("检测到端口占用，尝试强制重启网络...")
            ap.active(False)
            utime.sleep(1)
            init_ap()
            return run_web_server()
        else:
            raise
    finally:
        web_socket.close()
        utime.sleep(1)  # 确保端口释放

def connect_wifi():
    sta.active(True)
    sta.connect(wifi_ssid, wifi_pass)
    
    for _ in range(20):
        if sta.isconnected():
            print("连接成功! IP:", sta.ifconfig()[0])
            led.value(1)
            return True
        utime.sleep(1)
        led.value(not led.value())
    
    print("连接失败")
    led.value(0)
    return False

def start_provisioning():
    global scan_results
    led.value(0)
    
    # 初始化AP模式
    init_ap()
    
    # 扫描WiFi
    scan_results = scan_wifi()
    print("扫描到SSID:", scan_results)
    
    # 启动Web服务器
    run_web_server()
    
    # 尝试连接WiFi
    if wifi_ssid:
        if connect_wifi():
            return True
    return False

if __name__ == "__main__":
        # 配网流程
        while not sta.isconnected():
            print("进入配网模式...")
            if start_provisioning():
                print("配网成功!")
                break
            print("配网失败，重启流程...")
            utime.sleep(2)