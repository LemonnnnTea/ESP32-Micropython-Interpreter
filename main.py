import network
import socket
import uselect as select
import gc
import ubinascii as binascii
import uhashlib as hashlib
import os
import sys
import time


_original_print = print

SSID = "1"
PASSWORD = "12345678"
WS_PORT = 8266

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        _original_print('已经连接到WiFi')
        _original_print('网络配置:', wlan.ifconfig())
        return wlan.ifconfig()[0]
    
    _original_print('正在连接WiFi:', SSID)
    wlan.connect(SSID, PASSWORD)
    
    max_wait = 30
    while max_wait > 0:
        if wlan.isconnected():
            break
        max_wait -= 1
        time.sleep(1)
    
    if wlan.isconnected():
        _original_print('WiFi连接成功!')
        config = wlan.ifconfig()
        _original_print('IP地址:', config[0])
        return config[0]
    else:
        _original_print('WiFi连接失败! 创建AP模式...')
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid='ESP32-WebIDE', password='12345678')
        time.sleep(2)
        
        if ap.active():
            config = ap.ifconfig()
            _original_print('AP模式已启动 - IP:', config[0])
            return config[0]
        else:
            _original_print('AP模式启动失败')
            return None

def websocket_handshake(client):
    try:
        _original_print("开始WebSocket握手...")
        data = b""
        client.setblocking(False)
        
        start_time = time.time()
        while time.time() - start_time < 5:
            try:
                chunk = client.recv(256)
                if chunk:
                    data += chunk
                    if b"\r\n\r\n" in data:
                        break
            except OSError:
                time.sleep(0.1)
        
        if not data:
            return False
            
        request = data.decode('utf-8')
        
        lines = request.split('\r\n')
        headers = {}
        for line in lines[1:]:
            if ': ' in line:
                key, value = line.split(': ', 1)
                headers[key.lower()] = value
        
        if ('upgrade' in headers.get('connection', '').lower() and 
            headers.get('upgrade', '').lower() == 'websocket'):
            
            key = headers.get('sec-websocket-key', '')
            if not key:
                return False
                
            key += '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
            key_hash = hashlib.sha1(key.encode()).digest()
            accept_key = binascii.b2a_base64(key_hash).decode().strip()
            
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Accept: " + accept_key + "\r\n"
                "\r\n"
            )
            client.send(response.encode())
            _original_print("WebSocket握手成功!")
            return True
        return False
            
    except Exception as e:
        _original_print("握手错误:", e)
        return False

def websocket_receive(client):
    try:
        client.setblocking(False)
        
        header = b""
        start_time = time.time()
        while len(header) < 2 and time.time() - start_time < 2:
            try:
                chunk = client.recv(2 - len(header))
                if chunk:
                    header += chunk
            except OSError:
                time.sleep(0.01)
        
        if len(header) < 2:
            return None
            
        byte1, byte2 = header[0], header[1]
        opcode = byte1 & 0x0F
        if opcode != 1:
            return None
            
        masked = byte2 & 0x80
        payload_length = byte2 & 0x7F
        
        extra_len = 0
        if payload_length == 126:
            extra_len = 2
        elif payload_length == 127:
            extra_len = 8
        
        if extra_len > 0:
            length_data = b""
            start_time = time.time()
            while len(length_data) < extra_len and time.time() - start_time < 2:
                try:
                    chunk = client.recv(extra_len - len(length_data))
                    if chunk:
                        length_data += chunk
                except OSError:
                    time.sleep(0.01)
            
            if len(length_data) < extra_len:
                return None
            
            if payload_length == 126:
                payload_length = (length_data[0] << 8) | length_data[1]
            else:
                return None
        
        mask_key = None
        if masked:
            mask_key = b""
            start_time = time.time()
            while len(mask_key) < 4 and time.time() - start_time < 2:
                try:
                    chunk = client.recv(4 - len(mask_key))
                    if chunk:
                        mask_key += chunk
                except OSError:
                    time.sleep(0.01)
            
            if len(mask_key) < 4:
                return None
        
        payload = b""
        start_time = time.time()
        timeout = 3 + (payload_length / 1000) 
        while len(payload) < payload_length and time.time() - start_time < timeout:
            try:
                chunk = client.recv(payload_length - len(payload))
                if chunk:
                    payload += chunk
            except OSError:
                time.sleep(0.01)
        
        if len(payload) < payload_length:
            return None
        
        if masked and mask_key:
            decoded = bytearray(payload_length)
            for i in range(payload_length):
                decoded[i] = payload[i] ^ mask_key[i % 4]
            payload = decoded
        
        return payload.decode('utf-8')
        
    except Exception as e:
        return None

def websocket_send(client, text):
    try:
        data = text.encode('utf-8')
        length = len(data)
        
        frame = bytearray()
        frame.append(0x81)
        
        if length <= 125:
            frame.append(length)
        elif length <= 65535:
            frame.append(126)
            frame.extend(length.to_bytes(2, 'big'))
        else:
            frame.append(127)
            frame.extend(length.to_bytes(8, 'big'))
        
        frame.extend(data)
        client.send(bytes(frame))
        return True
        
    except Exception as e:
        return False

# 文件操作函数
def save_file(filename, content):
    try:
        with open(filename, 'w') as f:
            f.write(content)
        return True, f"文件 '{filename}' 保存成功"
    except Exception as e:
        return False, f"保存文件错误: {e}"

def read_file(filename):
    try:
        with open(filename, 'r') as f:
            content = f.read()
        return True, content
    except Exception as e:
        return False, f"读取文件错误: {e}"

def list_files():
    try:
        files = os.listdir()
        return True, files
    except Exception as e:
        return False, []

def delete_file(filename):
    try:
        os.remove(filename)
        return True, f"文件 '{filename}' 删除成功"
    except Exception as e:
        return False, f"删除文件错误: {e}"

def file_exists(filename):
    try:
        files = os.listdir()
        return filename in files
    except:
        return False

# 自定义print函数来捕获输出
output_buffer = []

def custom_print(*args, **kwargs):
    """自定义print函数，将输出保存到缓冲区"""
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    
    output_str = sep.join(str(arg) for arg in args) + end
    
    output_buffer.append(output_str)
    
    _original_print(*args, **kwargs)


def execute_code_safely(code):
    """安全执行代码并捕获输出"""
    global output_buffer
    output_buffer = []
    
    env = {
        'os': os, 'gc': gc, 'sys': sys, 'time': time,
        'print': custom_print,  
    }
    
    try:
        try:
            result = eval(code, env)
            if result is not None:
                output_buffer.append(f"表达式结果: {result}\n")
            return True, "执行完成", "".join(output_buffer)
        except:
            exec(code, env)
            return True, "执行完成", "".join(output_buffer)
            
    except Exception as e:
        return False, f"执行错误: {e}", "".join(output_buffer)

def run_python_file_safely(filename):
    """安全运行Python文件"""
    global output_buffer
    output_buffer = []
    
    try:
        if not file_exists(filename):
            return False, f"文件 '{filename}' 不存在", ""
        
        success, content = read_file(filename)
        if not success:
            return False, content, ""
        
        success, result, output = execute_code_safely(content)
        return success, result, output
        
    except Exception as e:
        return False, f"运行文件错误: {e}", "".join(output_buffer)

def execute_command(command, client):
    """执行命令"""
    try:
        command = command.strip()
        _original_print(f"执行命令 (前100字符): {command[:100]}")  
        
        if command.startswith("SAVE:"):
            parts = command.split(":", 2)
            if len(parts) == 3:
                filename = parts[1]
                content = parts[2]
                success, result = save_file(filename, content)
                websocket_send(client, f"{result}\n")
                return result
            return "保存命令格式错误，使用: SAVE:filename:content"
        
        elif command.startswith("READ:"):
            parts = command.split(":", 1)
            if len(parts) == 2:
                filename = parts[1]
                success, content = read_file(filename)
                if success:
                    websocket_send(client, f"FILE_CONTENT:{content}")
                    return f"已读取文件: {filename}"
                else:
                    websocket_send(client, f"{content}\n")
                    return content
            return "读取命令格式错误，使用: READ:filename"
        
        elif command.startswith("RUN:"):
            parts = command.split(":", 1)
            if len(parts) == 2:
                filename = parts[1]
                websocket_send(client, f"开始运行文件: {filename}\n")
                websocket_send(client, "=" * 40 + "\n")
                
                success, result, output = run_python_file_safely(filename)
                
                if output:
                    websocket_send(client, output)
                
                websocket_send(client, "=" * 40 + "\n")
                
                if success:
                    websocket_send(client, f"文件运行完成: {result}\n")
                else:
                    websocket_send(client, f"文件运行失败: {result}\n")
                
                return result
            return "运行命令格式错误，使用: RUN:filename"
        
        elif command == "LIST" or command == "ls":
            success, files = list_files()
            if success:
                json_files = '[' + ','.join([f'"{f}"' for f in files]) + ']'
                result = f"文件列表: {json_files}"
                websocket_send(client, f"{result}\n")
                return result
            else:
                websocket_send(client, f"获取文件列表失败: {files}\n")
                return "获取文件列表失败"
        
        elif command.startswith("DELETE:"):
            parts = command.split(":", 1)
            if len(parts) == 2:
                filename = parts[1]
                success, result = delete_file(filename)
                websocket_send(client, f"{result}\n")
                return result
            return "删除命令格式错误，使用: DELETE:filename"
        
        elif command.startswith("EXISTS:"):
            parts = command.split(":", 1)
            if len(parts) == 2:
                filename = parts[1]
                exists = file_exists(filename)
                result = f"文件 '{filename}' 存在: {exists}"
                websocket_send(client, f"{result}\n")
                return result
            return "检查命令格式错误，使用: EXISTS:filename"
        
        elif command == "help" or command == "HELP":
            help_text = """
=== MicroPython Web IDE 命令 ===

文件操作:
  LIST / ls               - 列出文件
  READ:filename           - 读取文件内容 (在编辑器显示)
  SAVE:filename:content   - 保存文件 (内容从编辑器获取)
  DELETE:filename         - 删除文件
  EXISTS:filename         - 检查文件是否存在

Python代码:
  直接输入代码或使用 '运行文件' 按钮执行
            """
            websocket_send(client, f"{help_text}\n")
            return "显示帮助信息"
        
        else:
            websocket_send(client, "执行代码:\n")
            websocket_send(client, "-" * 20 + "\n")
            
            success, result, output = execute_code_safely(command)
            
            if output:
                websocket_send(client, output)
            
            websocket_send(client, "-" * 20 + "\n")
            
            if success:
                websocket_send(client, f"执行结果: {result}\n")
            else:
                websocket_send(client, f"执行失败: {result}\n")
            
            return result
            
    except Exception as e:
        error_msg = f"执行错误: {e}"
        _original_print(error_msg) 
        websocket_send(client, f"{error_msg}\n")
        return error_msg

def handle_client(client, addr):
    _original_print(f"处理客户端: {addr}")
    
    try:
        if not websocket_handshake(client):
            client.close()
            return
        
        welcome_msg = """=== MicroPython Web IDE ===
连接成功!

输入 'help' 查看可用命令
所有print输出都会实时显示在终端中
"""
        websocket_send(client, welcome_msg)
        
        last_activity = time.time()
        while True:
            try:
                poller = select.poll()
                poller.register(client, select.POLLIN)
                events = poller.poll(1000)
                
                if events:
                    message = websocket_receive(client)
                    if message is None:
                        break
                    
                    if message.strip():
                        last_activity = time.time()
                        if len(message) > 100:
                             websocket_send(client, f">>> {message[:100]}...\n")
                        else:
                             websocket_send(client, f">>> {message}\n")
                        
                        execute_command(message, client)
                        gc.collect()
                else:
                    if time.time() - last_activity > 300:
                        break
                        
            except Exception as e:
                _original_print(f"处理消息错误: {e}")
                break
                
    except Exception as e:
        _original_print(f"客户端处理错误: {e}")
    finally:
        try:
            client.close()
        except:
            pass
        _original_print(f"客户端 {addr} 断开连接")

def start_server():
    ip = connect_wifi()
    if ip is None:
        return
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', WS_PORT))
    server_socket.listen(1)
    server_socket.setblocking(False)
    
    _original_print(f"服务器运行在: {ip}:{WS_PORT}")
    
    client_count = 0
    poller = select.poll()
    poller.register(server_socket, select.POLLIN)
    
    while True:
        try:
            events = poller.poll(1000)
            
            if events:
                client, addr = server_socket.accept()
                client_count += 1
                _original_print(f"连接 #{client_count} from {addr}")
                handle_client(client, addr)
            
            gc.collect()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(1)
    
    server_socket.close()

_original_print("启动MicroPython Web IDE服务器...")
start_server()