from bottle import route, post, get, run, template, static_file, request, response, auth_basic
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import os
import time
import json
import sys
import socket

sys.path.append("/media/usb/apps")
from pocca.utils.app import App # Application Manager (Settings / Secrets / utilities)

app = App()
USERNAME = app.secrets["USER"]["name"]
PASSWORD = app.decoder.decode(app.secrets["USER"]["password"])
if PASSWORD is False:
    PASSWORD = app.secrets["USER"]["password"]

images_folder = app.settings["FOLDERS"]["images"]
temp_folder = app.settings["FOLDERS"]["temp"]

# https://xiaoouwang.medium.com/create-a-watchdog-in-python-to-look-for-filesystem-changes-aaabefd14de4
users = set()
last_image = {}

def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False

    return True

# Get last image data from file /last_image.json
def get_last_image():
    global last_image
    try:
        with open(temp_folder + "/last_image.json", "r") as f:
            last_image = json.loads(f.read())
    except:
        print("👀🖼️ ❌ Error reading last image data")
        last_image["filename"] = ""
        last_image["timestamp"] = ""
    # Add sync = true to last_image
    # return last_image json
    return last_image

# Return list of images available in images_folder
def get_images_list():
    images = []
    for image in os.listdir(images_folder):
        if image.endswith(".jpg") or image.endswith(".png") or image.endswith(".gif"):
            images.append(images_folder + "/" + image)
    try:
        images = sorted(images, key = os.path.getmtime)
    except:
        for image in os.listdir(images_folder):
            if image.endswith(".jpg") or image.endswith(".png") or image.endswith(".gif"):
                images.append(images_folder + "/" + image)
        images = sorted(images, key = os.path.getmtime)

    for images in images:
        # Get only basename in image
        images = os.path.basename(images)
    return images

# Return device informations
def get_device_info(auth, event):
    json_images = []
    json_return = {}
    json_return["name"] = app.system.info["hostname"]
    json_return["type"] = app.system.info["current_app"]
    json_return["ip"] = app.system.getIP()
    json_return["auth"] = auth
    if auth:
        json_return["inuse"] = os.path.exists("/media/usb/.usbaccess")
        json_return["last_image"] = get_last_image()
        json_return["images"] = get_images_list()

    json_return["event"] = event
    # Return json_return as string
    return json_return

class fileWatcher(FileSystemEventHandler):

    def on_modified(self, event):
        global last_image
        if not event.is_directory:
            for user in users:
                for auth_ip in auth_ips:
                    if user.environ["REMOTE_ADDR"] == auth_ip:
                        # Wait for image to be copied
                        time.sleep(0.01)
                        device_info = get_device_info(True, event="newpictures")
                        print("--> New Picture 🖼️: " + device_info["last_image"]["filename"])
                        if device_info["last_image"]["filename"] != last_image:
                            last_image = device_info["last_image"]["filename"]
                            user.send(json.dumps(device_info))
                        # Send last image data to user

event_handler = fileWatcher()
my_observer = Observer()
my_observer.schedule(event_handler, temp_folder + "/last_image.json", recursive=False)
try:
    my_observer.start()
except:
    # Create a file name last_image.json
    with open(temp_folder + "/last_image.json", "w") as f:
        f.write('{"filename":"", "timestamp":""}')
    my_observer.start()

def is_authenticated_user(user, password):
    # print("Authentication...")
    # You write this function. It must return
    # True if user/password is authenticated, or False to deny access.
    if user == USERNAME and password == PASSWORD:
        return True
    else:
        print("❌ 👮‍♂️🤚 Wrong Password :" + password)
        return False

@route("/")
def state():
    return "alive"

@route("/restart")
@auth_basic(is_authenticated_user)
def restart():
    os.system("reboot")
    return "ok"

@route("/remote")
@auth_basic(is_authenticated_user)
def remote():
    return "Not Implemented"

@route("/delete/<image>")
@auth_basic(is_authenticated_user)
def delete(image="none"):
    print("🗑️ ⬅️ 🖼️ Delete " + image)
    if(os.path.exists(images_folder + "/" + image)):
        os.remove(images_folder + "/" + image )
        return "deleted"
    else:
        return "error"

@route("/deleteall")
@auth_basic(is_authenticated_user)
def deleteall():
    # Delete all files in images_folder
    print("🗑️ ⬅️ 🖼️ Delete all pictures")
    error = False
    for image in os.listdir(images_folder):
        #print(image)
        #print(images_folder)
        if image.endswith(".jpg") or image.endswith(".png") or image.endswith(".gif"):
            os.remove(images_folder + "/" + image)
            with open(temp_folder + "/last_image.json", "w") as f:
                f.write('{"filename":"", "timestamp":""}')
        else:
            error = True
    if error:
        return "error"
    else:
        return "ok"

@route("/list")
@auth_basic(is_authenticated_user)
def list():
    return get_device_info()

# Return images file in images_folder
@route("/images/<filepath:path>")
def images(filepath):
    return static_file(filepath, root=images_folder)

auth_ips = []

# Generate a websocket for each user
@get('/websocket', apply=[websocket])
def echo(ws):
    # On connection, add user to users set and check if authorized
    users.add(ws)
    auth = False

    for auth_ip in auth_ips:
        if ws.environ["REMOTE_ADDR"] == auth_ip:
            print("🟩 👮👌 Already Authorized User:" + ws.environ["REMOTE_ADDR"])
            auth = True
        else:
            print("❌ 👮✋ User not authorized :" + ws.environ["REMOTE_ADDR"])

    ws.send(json.dumps(get_device_info(auth, event="login")))

    while True:
        msg = ws.receive()
        if msg is not None:
            auth = False
            for auth_ip in auth_ips:
                if ws.environ["REMOTE_ADDR"] == auth_ip:
                    auth = True
                    # Send last image data as json with sync = true to the json
                    if msg == "sync":
                        ws.send(json.dumps(get_device_info(auth, event="sync")))
                    elif msg == "ping":
                        ws.send("pong")
                    else:
                        ws.send("command:sync,ping")
            if auth is False:
                if is_authenticated_user("pi", msg.strip()):
                    auth_ips.append(ws.environ["REMOTE_ADDR"])
                    auth = True
                else:
                    auth = False

                ws.send(json.dumps(get_device_info(auth, event="login")))
        else:
            break

    users.remove(ws)

run(host="0.0.0.0", port=80, server=GeventWebSocketServer)
