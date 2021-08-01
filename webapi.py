from bottle import route, post, get, run, template, static_file, request, response, auth_basic
import os
import imghdr
images_folder = "/media/usb/images"
import json
import configparser
import socket
import subprocess
name = socket.gethostname()
settings = configparser.ConfigParser()
settings.read("/media/usb/pocca.ini")
USERNAME = settings["APPLICATION"]["user"]
PASSWORD = settings["APPLICATION"]["password"]
TYPE = settings["APPLICATION"]["type"]
ip = subprocess.check_output(["hostname", "-I"])
ip = ip.decode()
ip = ip.split(" ")[0]


def is_authenticated_user(user, password):
    # You write this function. It must return
    # True if user/password is authenticated, or False to deny access.
    if user == USERNAME and password == PASSWORD:
        return True
    else:
        return False

@route("/")
def state():
    return "alive"

@route("/restart")
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
    print("Deleting")
    if(os.path.exists(images_folder + "/" + image)):
        os.remove(images_folder + "/" + image )
        return "deleted"
    else:
        return "error"

@route("/list")
@auth_basic(is_authenticated_user)
def list():
    json_images = []
    json_return = {}
    for image in os.listdir(images_folder):
        if os.path.exists(images_folder + "/" + image):
            try:
                os.rename(images_folder + "/" + image, images_folder + "/" + image)
                print('Access on file "' + image +'" is available!')
                check_images = imghdr.what(images_folder + "/" + image)
                print(check_images)
                if check_images != None:
                    json_images.append(image)
            except OSError as e:
                print('Access-error on file "' + image + '"! \n' + str(e))
    json_return["name"] = name
    json_return["images"] = json_images
    json_return["type"] = TYPE
    json_return["ip"] = ip
    #print(json_return)
    return json.dumps(json_return)

@route("/images/<filepath:path>")
def images(filepath):
    print("Get Images")
    return static_file(filepath, root=images_folder)

run(host="0.0.0.0", port=80)
