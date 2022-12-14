import json
import joblib
import random
import requests
import threading

import selenium
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import traceback
import time
import os
from urllib.parse import quote

from utils import *


with open("config.json") as f:
    config = json.load(f)
PATH_TO_DRIVER = config["chromeDriverPath"]

EMAIL = "awehof111@gmail.com"
# well, people usually say skeleton key, but this email is "skeleton" enough to me
SKELETONEMAIL = "john@gmail.com"
PASSWORD = "8FQXeIIlTj"
STTIME = time.time()
stopFlag = False

DEBUG = False
webdriver.chrome.slientLogging = True


def log(msg):
    if DEBUG:
        print(
            "%s %s"
            % (time.strftime("%H:%M:%S", time.gmtime(time.time() - STTIME)), str(msg))
        )


recaptchaJS = loadJS("recaptcha.js")
evasionJS = loadJS("evasion.js")


def create_driver(proxy=False):

    proxies = [
        "128.173.237.66",
        "69.30.240.226:15002",
        "69.30.197.122:15002",
        "142.54.177.226:15002",
        "198.204.228.234:15002",
        "195.154.255.118:15002",
        "195.154.222.228:15002",
        "195.154.252.58:15002",
        "195.154.222.26:15002",
        "63.141.241.98:16001",
        "173.208.209.42:16001",
        "163.172.36.211:16001",
        "163.172.36.213:16001",
    ]

    caps = DesiredCapabilities.CHROME
    caps["goog:loggingPrefs"] = {"performance": "ALL"}
    caps["loggingPrefs"] = {"performance": "ALL"}

    chrome_options = webdriver.ChromeOptions()

    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation", "load-extension"]
    )
    chrome_options.add_experimental_option("useAutomationExtension", False)

    chrome_options.add_experimental_option(
        "prefs", {"profile.default_content_setting_values.notifications": 2, }
    )

    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")

    # chrome_options.add_argument("--load-extension=" + os.path.abspath('RigRecaptcha/'))

    # chrome_options.add_argument('--disable-extensions')
    # chrome_options.add_argument("--disable-notifications")

    if not DEBUG:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    # chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument("--log-level=3")

    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
    )
    chrome_options.add_argument("window-size=1536,824")
    if proxy:
        chrome_options.add_argument(
            "--proxy-server={}".format(proxies[random.randint(0, 15)])
        )
    driver = None
    while driver == None:
        try:

            driver = webdriver.Chrome(
                executable_path=PATH_TO_DRIVER,
                options=chrome_options,
                desired_capabilities=caps,
            )
        except Exception as e:
            pass
    driver.set_page_load_timeout(60)

    # install different javascript
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "onbeforeunload = alert = prompt = confirm = function(){};"},
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {"source": evasionJS}
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {"source": recaptchaJS}
    )
    driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*://*/*recaptcha*"]})
    return driver


buttonDetectionScript = loadJS("detectButtons.js")
getFeaturesScript = loadJS("prelimFilter.js")

# fieldnames = ['tag', 'account', 'email', 'innertextLength',  # 'loc_bottom', 'loc_left', 'loc_right', 'loc_top',
#               'next', 'oauth', 'password', 'signIn', 'signup', 'visible', 'changeable', 'isSameDomain']
# tag2num = {'img': 1, 'iframe': 2, 'li': 3, 'button': 4, 'span': 5,
#            'i': 6, 'input': 7, 'font': 8, 'div': 9, 'a': 10, 'p': 11}


# def getFeatures(sample):
#     features = sample[1]
#     tag = features["tag"].lower()
#     if tag in tag2num:
#         features["tag"] = tag2num[tag]
#     else:
#         features["tag"] = 0
#     row = []
#     for key in fieldnames:
#         if type(features[key]) == type(0.2):
#             row.append(round(features[key], 2))
#         elif type(features[key]) == type(True):
#             row.append(int(features[key]))
#         else:
#             row.append(features[key])
#     return row


def scoreLogin(f):
    score = 0
    # Had to do fraction because this number should only differentiate elements
    # within the same category 
    score += f["login"] * 0.1
    score += f["account"] * 0.01
    score += f["email"] * 0.01

    if f["innertextLength"] > 5:
        score = -999
    if f["visible"]:
        score += 8
    if f["tag"].strip() == "iframe":
        if not f["visible"]:
            score = -999
        score += 4
    if f["hasLink"] or f["changeable"]:
        score += 2
        if f["isSameDomain"]:
            score += 2
    else:
        score = -999
    return score


def scoreAccount(f):
    return f["account"] + f["login"] + f["email"]


def scorePassword(f):
    return f["password"]


def detectButtons(driver):
    log("Detecting buttons...")

    samples, dfsSeq = driver.execute_script(getFeaturesScript, DEBUG)

    currUrl = driver.current_url

    classNames = {}

    for sample in samples:
        className = sample[1]["className"]
        if len(list(filter(None, className.split(' ')))) > 1:
            classNames[className] = classNames.get(className, 0) + 1
            

    buttons = {"login": [], "account": [], "password": [], "recaptcha": [],
               "oauth": [], "submit": []}  # TODO: recaptcha oauth submit

    newSamples = []
    for sample in samples:
        if stopFlag:
            raise selenium.common.exceptions.TimeoutException
        el = sample[0]
        features = sample[1]

        if features["oauth"] > 0:
            buttons["oauth"].append(el)
            continue

        if features["trash"] > 0:
            continue

        if classNames.get(features["className"], 0) > 3:
            continue

        if isStale(el):
            continue

        features["visible"] = userSeeable(el)
        features["changeable"] = userChangeable(el)
        url = el.get_attribute("href") or el.get_attribute("src")
        features["hasLink"] = False
        if url is not None and not url.startswith("javascript:") and currUrl.split("#")[0] != url.split("#")[0]:
            features["hasLink"] = True
        features["isSameDomain"] = False
        if features["hasLink"] and isSameDomain(currUrl, url):
            features["isSameDomain"] = True
        newSamples.append(sample)
    samples = newSamples

    hasLogin = False

    for sample in samples:
        el = sample[0]
        features = sample[1]
        if features["emailPasswordSelected"]:      
            # entering here means that the element *must* be a text input, so it
            # can in no case be a login button unless the website creator is crazy
            if features["visible"] and features["changeable"] and features["signup"] == 0:
                # if features["password"] == 0:  # the account keywords is too general, a password input may contain them
                el.___wantsEmail = features["email"] > 0

                if features["account"] + features["login"] > 0:
                    hasLogin = True

                if features['type'].strip().lower() == 'password':
                    buttons["password"].append([el, scorePassword(features)])
                else:
                    buttons["account"].append([el, scoreAccount(features)])

            if features["password"] > 0:
                hasLogin = True

        elif features["login"] > 0 or features["account"] > 0 or features['email'] > 0:
            buttons["login"].append([el, scoreLogin(features)])

    for g in ["login", "account", "password"]:
        buttons[g].sort(key=lambda x: x[1], reverse=True)
        buttons[g] = [button[0] for button in buttons[g] if button[1] > 0]

    if not hasLogin:
        buttons["account"] = []

    if DEBUG:
        driver.execute_script("debugButtons = arguments[0]; enableNextFunc(debugButtons);", buttons)

    return buttons


def toLoginPage(driver, btns, status):
    rtn = "samePage"
    currUrl = driver.current_url

    btnsHTML = driver.execute_script("return arguments[0].map(el=>el.outerHTML)", btns)
    btnsHTML.reverse()

    for i in btns:
        btnHTML = btnsHTML.pop()
        if isStale(i):
            continue
        url = i.get_attribute("href")
        elHash = "%d, %d, %d, %d" % (
            i.rect["x"],
            i.rect["y"],
            i.rect["width"],
            i.rect["height"],
        )
        if elHash in status["visitedEls"]:
            continue
        if (
            i.tag_name.lower().strip() == "a"
            and url
            and not url.startswith("javascript:")
            and currUrl.split("#")[0] != url.split("#")[0]
        ):
            try:
                i.click()
            except:
                driver.get(url)
        elif i.tag_name.lower().strip() == "iframe":
            try:
                switchToFrame(driver, i, status)
                # driver.switch_to.frame(i)
            except:
                continue
            log("iframe detected")
            rtn = "iframe"
        else:
            try:
                i.click()
            except Exception as e:
                continue
        status["buttonClicked"].append(btnHTML)
        status["visitedEls"].append(elHash)
        time.sleep(1)
        if (
            len(driver.window_handles) > 1
            and driver.window_handles[len(driver.window_handles) - 1]
            != driver.current_window_handle
        ):
            driver.switch_to.window(
                driver.window_handles[len(driver.window_handles) - 1]
            )
            log("Another tab detected")
        if driver.current_url != currUrl and rtn == "samePage":
            # as we have entered a new page, current frame should get reset
            status["currentFrames"] = []
            rtn = "newPage"
        return rtn


# Example: https://sbu.ac.ir/
def checkHttpAuth(driver, status={}):
    log = driver.get_log("performance")
    for entry in log:
        message = json.loads(entry["message"])["message"]
        if (
            message["method"] == "Network.responseReceived"
            and message["params"]["response"]["status"] == 401
        ):
            url = message["params"]["response"]["url"]
            headers = message["params"]["response"]["headers"]
            auth = caseInsensitiveGet(headers, "WWW-Authenticate")
            if auth:
                status["httpAuth"] = auth
                for i in auth.split("\n"):
                    if i.split(" ")[0].lower() in [
                        "basic",
                        "digest",
                        "ntlm",
                        "negotiate",
                    ]:
                        ip = message["params"]["response"].get('remoteIPAddress')
                        viaArr = [ip]
                        via = caseInsensitiveGet(headers, "via")
                        if via:
                            viaArr.append(via)
                        return [["password email ", url, viaArr]]


def getAccountServerURL(driver, skeletonEmailUsed=False):
    password = PASSWORD
    if skeletonEmailUsed:
        email = SKELETONEMAIL
    else:
        email = EMAIL.split("@")[0]

    passwords = [password, b64encode(password)]
    emails = [email, b64encode(email)]

    if skeletonEmailUsed:
        emails.append(quote(email, encoding="utf-8"))

    recaptchaCode = "hahahahahahahahahahahahhahahaaahahahaha"

    requestsOfInterest = {}
    requestsOfInterestIds = []

    log = driver.get_log("performance")
    for entry in log:
        message = json.loads(entry["message"])["message"]
        if message["method"] == "Network.requestWillBeSent":
            url = message["params"]["request"]["url"]

            if url.startswith("https://translate.googleapis.com"):
                continue

            if message["params"]["request"]["method"] == "POST":
                if "postData" in message["params"]["request"]:
                    stringOfInterest = message["params"]["request"]["postData"]
                else:
                    try:
                        stringOfInterest = driver.execute_cdp_cmd(
                            "Network.getRequestPostData",
                            {"requestId": message["params"]["requestId"]},
                        )["postData"]
                    except:
                        continue
                stringOfInterest += " " + url
            elif message["params"]["request"]["method"] == "GET":
                stringOfInterest = url
            else:
                # just for the sake of not forgetting anything
                stringOfInterest = url

            description = ""

            if strHasArrEl(stringOfInterest, passwords):
                description += "password "
            if strHasArrEl(stringOfInterest, emails):
                description += "email "
            if recaptchaCode in stringOfInterest:
                description += "recaptcha "

            if description:
                requestId = message["params"]["requestId"]
                if requestId in requestsOfInterest:
                    requestsOfInterest[requestId]["url"].append(url)
                    requestsOfInterest[requestId]["description"].append(description)
                else:
                    requestsOfInterestIds.append(requestId)
                    requestsOfInterest[requestId] = {
                        "description": [description],
                        "url": [url],
                        "serverKnowledge": [],
                    }

        elif message["method"] == "Network.responseReceived":
            requestId = message["params"]["requestId"]
            if strHasArrEl(requestId, requestsOfInterestIds):
                ip = message["params"]["response"].get('remoteIPAddress')
                requestsOfInterest[requestId]["serverKnowledge"].append(ip)

                headers = message["params"]["response"]["headers"]
                via = caseInsensitiveGet(headers, "via")
                if via:
                    requestsOfInterest[requestId]["serverKnowledge"].append(via)

    requestUrls = []

    for i in requestsOfInterest:
        request = requestsOfInterest[i]
        for idx, val in enumerate(request["description"]):
            requestUrls.append(
                [request["description"][idx], request["url"][idx], request["serverKnowledge"]]
            )

    return requestUrls


def processFrame(driver, status, wait=True):
    log("Processing frame, current depth = %d" % status["depth"])

    httpAuth = checkHttpAuth(driver, status)
    if httpAuth:
        return httpAuth

    translatePage(driver)

    if wait:
        # the page has changed. wait for more time
        if waitUntilSelection(driver, "form", 10):
            time.sleep(5)
    else:
        # for waiting the page to translate
        time.sleep(1)

    switchToAutoFocusedInputElementFrame(driver, status)

    buttons = detectButtons(driver)

    status["recaptchaCount"] += len(buttons["recaptcha"])
    status["loginCount"] += len(buttons["login"])
    status["oauthCount"] += len(buttons["oauth"])

    # let's only continue if there's an email input
    if buttons["account"]:
        status["accountCount"] = len(buttons["account"])
        log("Account input detected. Sending fake accounts")

        urls = []

        skeletonEmailUsed = False

        # clear distracting loggingPrefs
        driver.get_log("performance")

        if not buttons["password"]:
            skeletonEmailUsed = True
            status["twoStepLogin"] = True

            accountInput = buttons["account"][0]

            account = SKELETONEMAIL
            if not accountInput.___wantsEmail:
                account = account.split("@")[0]
            try:
                accountInput.click()
                time.sleep(0.3)
            except:
                pass
            sendKeys(driver, accountInput, account)
            # accountInput.send_keys(account)
            time.sleep(0.2)
            sendKeys(driver, accountInput, webdriver.common.keys.Keys.ENTER)
            # accountInput.send_keys(webdriver.common.keys.Keys.ENTER)

            time.sleep(5)
            buttons = detectButtons(driver)
            buttons["account"] = []

        status["passwordCount"] = len(buttons["password"])

        for i in buttons["account"]:
            if userChangeable(i):
                account = EMAIL
                if not i.___wantsEmail:
                    account = account.split("@")[0]
                try:
                    i.click()
                    time.sleep(0.3)
                except:
                    pass

                sendKeys(driver, i, account + webdriver.common.keys.Keys.TAB)
                # i.send_keys(account)
                # i.send_keys(webdriver.common.keys.Keys.TAB)

        for i in buttons["password"]:
            if userChangeable(i):
                try:
                    i.click()
                    time.sleep(0.3)
                except:
                    pass

                sendKeys(driver, i, PASSWORD)
                # i.send_keys(PASSWORD)
                # i.send_keys(webdriver.common.keys.Keys.TAB)
                status["passwordEntered"] = True

        if buttons["password"]:
            sendEnterKeyList = buttons["password"]
        else:
            sendEnterKeyList = buttons["account"]

        for i in buttons["recaptcha"]:
            driver.execute_script("arguments[0].click();", i)

        time.sleep(0.2)

        for i in sendEnterKeyList:
            if userChangeable(i):
                sendKeys(driver, i, webdriver.common.keys.Keys.ENTER)
                # i.send_keys(webdriver.common.keys.Keys.ENTER)
                time.sleep(3)
                urls = getAccountServerURL(driver, skeletonEmailUsed)
                if urls:
                    return urls

        for i in buttons["submit"]:
            if userChangeable(i):
                try:
                    i.click()
                except selenium.common.exceptions.ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", i)
                time.sleep(3)
                urls = getAccountServerURL(driver, skeletonEmailUsed)
                if urls:
                    return urls

        # for sites that don't have anything after entering email address (e.g. google)
        urls = getAccountServerURL(driver, skeletonEmailUsed)
        if urls:
            return urls

        log("No request with email or password captured")
        return urls

    elif buttons["recaptcha"]:
        driver.execute_script("grecaptcha.___handleAll();")
        time.sleep(1)
        urls = getAccountServerURL(driver)
        if urls:
            return urls

    nextPageType = toLoginPage(driver, buttons["login"], status)
    if nextPageType is None:
        return

    # nothing found. Let's continue
    # iframe switch should not consume depth
    if nextPageType == "iframe" or nextPageType == "newTab":
        status["depth"] += 1
    if status["depth"] > 0:
        # if isinstance(nextPageType, str) and nextPageType != "iframe":
        #     pass
        # translatePage(driver)

        # if we are switching to an iframe, we don't have to wait at all
        waitNeeded = nextPageType != "iframe"

        log("Going to a login page")
        status["depth"] -= 1
        return processFrame(driver, status, waitNeeded)


def processPage(driver, url):

    log("Start processing %s" % url)

    url = normalizeURL(url)

    driver.get(url)
    if not DEBUG:
        time.sleep(10)
        driver.refresh()

    urls = []

    initialDepth = 3

    status = {
        "accountCount": 0,
        "passwordCount": 0,
        "loginCount": 0,
        "recaptchaCount": 0,
        "oauthCount": 0,
        "twoStepLogin": False,
        "passwordEntered": False,
        "depth": initialDepth,
        "httpAuth": "",
        "buttonClicked": [],
        # entries below this will not go to the output status
        "currentFrames": [],
        "visitedEls": [],
    }

    samples = []

    urls = processFrame(driver, status)

    statusArr = [
        status["accountCount"],
        status["passwordCount"],
        status["loginCount"],
        status["recaptchaCount"],
        status["oauthCount"],
        status["twoStepLogin"],
        status["passwordEntered"],
        status["depth"],
        status["httpAuth"],
        status["buttonClicked"],
    ]

    if urls:
        log("Success")
        log(urls)
    else:
        log("Failed to detect login link. Exiting...")

    return (urls, statusArr)


def Stop():
    global stopFlag
    stopFlag = True


def crawlSingle(url):
    global stopFlag
    stopFlag = False

    driver = create_driver()
    timer = threading.Timer(240, Stop)
    timer.start()
    # result = processPage(driver, url)
    try:
        result = processPage(driver, url)
    except selenium.common.exceptions.TimeoutException:
        result = (
            ErrorCodes.FAILED_TO_LOAD,
            "Error: page failed to load: %s" % traceback.format_exc(5),
            []
        )
    except Exception as e:
        result = (ErrorCodes.CRASHED, "Error: program crashed: %s" % e, [])
    timer.cancel()
    driver.quit()

    return [url, result[0], result[1]]


if __name__ == "__main__":
    DEBUG = True
    # url = "pbase.com"
    url = "www.unimarconi.it"
    # rtn = getSelectedElement(driver)
    driver = create_driver()
    while True:
        result = processPage(driver, url)
    # result = crawlSingle(url)
    # print(json.dumps(result))
    # for x in result[3]:
    #     print(x)
