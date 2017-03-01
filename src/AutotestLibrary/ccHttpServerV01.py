#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
ccAutoTest: ccHttpServer
author: cdy
time: 2015-08-20 

"""

#__version__ = "0.1 by cdy"

#__all__ = ["ccHttpServer"]

import os
import sys
import types
import logging
import time
import robot.utils
import commands

reload(sys)
sys.setdefaultencoding('utf-8')

reqLogPath = "/usr/local/openresty/nginx/conf/cc.log"
ngxConfDestPath = "/usr/local/openresty/nginx/conf/vhost/VirtualHost.conf"
ngxExeFile = "/usr/local/openresty/nginx/sbin/nginx"
accessLogFile = "/usr/local/cdy/case/myapp.log"

#global 
handler=logging.FileHandler(accessLogFile)
formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class ccHttpServer(object):
    ROBOT_LIBRARY_SCOPE = 'Global'
    def __init__(self,origReqLogPath="",ngxConfDestPath=""):
        self.reqLogPath = origReqLogPath
        self.ngxConfDestPath = ngxConfDestPath
        self.reqSplitList=[]
    """
    ccReqLogSplit: 分析请求日志，split截断后存入属性list: reqInitlist，请求日志文件不存在，直接返回失败
    """
    def ccReqLogSplit(self,reqLogPath):
        logger.info("------------- start %s ----------***>>>"%sys._getframe().f_code.co_name)
        if os.path.isfile(reqLogPath):
            self.reqLogPath = reqLogPath
            try:
                fd = open(reqLogPath,"rb")
                data = fd.read()
                fd.close()
                #logger.info("msg in reqLogFile:\n%s"%data)
            except Exception,e:
                logger.error("Open or Read reqLogFile Failed: [%s]"%reqLogPath)
                return False
            self.reqSplitList = data.split("\r\n\r\n")
            return True
        else:
            logger.error("No reqLogFile: [%s]"%reqLogPath)
        return False
    """
    ccBytesToHttpRespone: 把单个的请求日志转换成字典形式，如下：
    {'method':'GET','ver':'HTTP/1.1','uri':'/cdy/2m.txt?a=1','headers':[[Name,Value],...,[Name,Value]]}
    """ 
    def _ccBytesToHttpRespone(self,reqBytes):
        reqDict = {}
        reqHeaders = []
        reqElement=reqBytes.split("\r\n")
        for i in range(len(reqElement)):
            if reqElement[i] == "":
                continue
            if i==0:
                reqLineList=reqElement[i].split(" ")
                reqLineItemsNum = len(reqLineList) 
                reqDict["meth"]=reqLineList[0] if reqLineItemsNum>0 else None
                reqDict["uri"]=reqLineList[1] if reqLineItemsNum>1 else None
                reqDict["ver"]=reqLineList[2] if reqLineItemsNum>2 else None
                if reqLineItemsNum !=3:
                    logger.error("Error req status Line: [%s]"%(reqElement[i]))
            else:
                colonIndex=reqElement[i].find(":")
                if colonIndex==-1:
                    headerName = reqElement[i]
                    headerValue = None
                    logger.error("No colon in header: [%s]"%(reqElement[i]))
                else:
                    headerName = reqElement[i][:colonIndex]
                    headerValue = reqElement[i][colonIndex+1:]
                if colonIndex == 0 or colonIndex == len(reqElement[i])-1:
                    logger.error("No header name or value: [%s]"%(reqElement[i]))
                reqHeaders.append((headerName.strip(' '),headerValue if headerValue is None else headerValue.strip()))
        reqDict["headers"]= reqHeaders 
        return reqDict

    """
    checkMode:
    -1:包含该头，0,
    """
    def _ccHeadersDictCheck(self,checkHeaders,headersPerReq,checkMode=0):         
        logger.info("------------- start %s ----------***>>>"%sys._getframe().f_code.co_name)
        if not headersPerReq:
            return False
        for key in checkHeaders.keys():
            lowHeaderName = key.lower()
            checkflag = False
            for i in range(len(headersPerReq)):
                if lowHeaderName==headersPerReq[i][0].lower() and checkHeaders[key]== headersPerReq[i][1]:
                    checkflag = True
                    logger.info("Check Header [%s] Succeed"%key)
                    break
            if not checkflag:
                logger.info("Check Header [%s:%s] Failed"%(key,checkHeaders[key]))
                return False
        return True        
    def _ccHeadersStrCheck(self,headerStr,strPerReq,checkMode="equal"):
        logger.info("------------- start %s ----------***>>>"%sys._getframe().f_code.co_name)
        return False if strPerReq.count(headerStr)==0 else True
    def _ccHeadersListCheck(self,headerList,strPerReq,checkMode="equal"):
        logger.info("------------- start %s ----------***>>>"%sys._getframe().f_code.co_name)
        for item in headerList:
            if strPerReq.count(item) ==0:
                return False
        return True
    """
    ccServerCheck: 检查回源请求
    checkMode:
        strict: 严格检查
        contain: 包含检查
    return: 返回匹配条件的请求数
    """              
    def ccServerCheck(self,uri,checkHeaders={},checkMeth="GET",checkVer="1.1",checkMode="strict",checkFile=reqLogPath): 
        logger.info("------------- start %s ----------*****>>>"%sys._getframe().f_code.co_name)
        #logger.info("------- %s ------"%type(checkHeaders))
        robotDictType = types.DictType
        if 'DotDict' in dir(robot.utils):
            robotDictType = robot.utils.dotdict.DotDict
        headerTypes = (types.DictType,types.ListType,types.StringType,types.UnicodeType,types.NoneType,robotDictType)
        uriTypes = (types.StringType,types.UnicodeType)     
        otherTypes = (types.StringType,types.UnicodeType,types.NoneType)
        if type(checkHeaders) not in headerTypes:
            logger.error("Type of checkHeaders [%s] not in [%s], Return -1 ..."%(type(checkHeaders),headerTypes))
            #logger.error(checkHeaders)
            return -1
       	if (type(uri) not in uriTypes):
            logger.error("Type of uri [%s] not in [%s], Return -2 ..."%(type(uri),uriTypes))
            return -2 
        if (type(checkMeth) not in otherTypes) or (type(checkVer) not in otherTypes) or (type(checkMode) not in otherTypes):
            logger.error("Type of others [%s,%s,%s] not in [%s], Return -3 ..." \
                %(type(checkMeth),type(checkVer),type(checkMode),otherTypes))
            return -3
        ### 便于使用，不再检查内存，每次check都读取请求日志文件，以保证请求记录都是最新的最全的
        # if self.reqSplitList==[]:
        res = self.ccReqLogSplit(checkFile) 
        if not res:
            logger.error("Split reqFile [%s] Failed, Return -4 ..."%checkFile)
            return -4
        ###
        checkCount= 0
        if os.stat(checkFile).st_size == 0:
            logger.info("No request in reqLogFile: [%s], Return -5 ..."%checkFile)
            return -5
        for i in range(len(self.reqSplitList)):
            checkReqLine = self.reqSplitList[i].split("\r\n")[0]
            if not self.reqSplitList[i] or uri not in checkReqLine:
                logger.info("uri [%s] not in reqSplitList[%s] [%s]"%(uri,i,self.reqSplitList[i]))
                continue
            dictPerReq = self._ccBytesToHttpRespone(self.reqSplitList[i])
            if uri == dictPerReq["uri"]:
                if checkMeth and checkMeth != dictPerReq["meth"]:
                    logger.warning("Uri matched, but CheckMeth [%s] Failed in reqSplitList[%s] [%s]" \
                        %(checkMeth,i,checkReqLine))
                    continue
                if checkVer and "HTTP/"+checkVer != dictPerReq["ver"]:
                    logger.warning("Uri matched, but CheckVer [%s] Failed in reqSplitList[%s] [%s]" \
                        %("HTTP/"+checkVer,i,checkReqLine))
                    continue
                if not checkHeaders:
                    logger.warning("All matched, CheckHeaders [%s] no check, reqLine [%s] checked Succeed in reqSplitList[%s] [%s]" \
                        %(checkHeaders,checkReqLine,i,self.reqSplitList[i]))
                    checkCount+=1
                    continue
                if isinstance(checkHeaders,dict) or isinstance(checkHeaders,robotDictType):
                    checkRes = self._ccHeadersDictCheck(checkHeaders, dictPerReq["headers"],checkMode)
                elif isinstance(checkHeaders,list):
                    checkRes = self._ccHeadersListCheck(checkHeaders,self.reqSplitList[i],checkMode)
                else:
                    checkRes = self._ccHeadersStrCheck(checkHeaders,self.reqSplitList[i],checkMode)
                    
                if checkRes:
                    logger.info("All matched, [%s,%s,%s,%s] checked Succeed in reqSplitList[%s] [%s]" \
                        %(uri,checkHeaders,checkMeth,checkVer,i,self.reqSplitList[i]))
                    checkCount+=1
                else:
                    logger.info("CheckHeaders Failed, [%s] checked Failed in reqSplitList[%s] [%s]" \
                        %(checkHeaders,i,self.reqSplitList[i]))
        return checkCount
    """
    APIName: ccRunCmd
    @Parameter:
        cmd: 执行命令
    @Return：
        return：执行成功 or 失败 
    """    
    def _ccRunCmd(self,cmd):
        status,output = commands.getstatusoutput(cmd)
        if status != 0:
            logger.error("Run cmd [%s] Failed: [%s]"%(cmd,output))
            return False
        logger.info("Run cmd [%s] Succeed!"%(cmd))
        return True
    """
    APIName: ccCleanReqLog: 清除请求日志。
    @Parameter:
        type: 
            both:清除源站nginx请求日志文件和解析好的数组请求，默认值
            file:只清除源站nginx请求日志文件
            mem:只清除解析好的存在内存中的数组请求
    """
    def ccCleanReqLog(self,reqLogFile=reqLogPath,cleanType="both",backup=False):
        logger.info("------------- start %s ----------***>>>"%sys._getframe().f_code.co_name)
        if not os.path.isfile(reqLogFile):
            logger.error("No reqLogFile [%s] exsit!"%reqLogFile)
            assert(False)
        bkRes = clFileRes = clMemRes = True
        if backup:
            cmd = "cp -f %s %s.%s"%(reqLogFile,reqLogFile,time.strftime("%Y%m%d%H%M%S"))
            bkres = self._ccRunCmd(cmd)
        if cleanType != "mem":
            cmd = ">"+reqLogFile
            clFileRes = self._ccRunCmd(cmd)
        if cleanType != "file":   
            self.reqSplitList = []
            logger.info("Clean reqSplitList in Mem Succeed!")
            clMemRes = True
        finalRes = bkRes and clFileRes and clMemRes
        logger.info("Clean ccCleanReqLog in mode [%s] %s!"%(cleanType, "Succeed" if finalRes else "Failed"))
        assert(finalRes)
    """
    APIName: ccSetRespone
    @Parameter:
    @Return:
    """
    def ccSetRespone(self,confInitPath,confDestPath=ngxConfDestPath,ngxFile=ngxExeFile,cpMode='force'):
        logger.info("------------- start %s ----------***>>>"%sys._getframe().f_code.co_name)
        if not os.path.isfile(confInitPath) or not os.path.isfile(ngxFile):
            logger.error("No expectConfFile [%s] or No ngxExeFile [%s]!"%(confInitPath,ngxFile))
            assert(False)
        rmRes = cpRes = checkConfRes = reloadRes = True
        if cpMode=='force' and os.path.isfile(confDestPath):
            rmRes = self._ccRunCmd("rm -f "+confDestPath)
        cpRes = self._ccRunCmd("cp -f "+confInitPath+" "+confDestPath) 
        checkConfRes = self._ccRunCmd(ngxFile+" -t") 
        reloadRes = self._ccRunCmd(ngxFile+" -s reload")
        if not reloadRes:
            reloadRes = self._ccRunCmd(ngxFile)
        finalRes = rmRes and cpRes and checkConfRes and reloadRes  
        logger.info("SetRespone in mode [%s] %s"%(cpMode,"Succeed" if finalRes else "Failed"))
        assert(finalRes)

if __name__ == '__main__':
    obj = ccHttpServer()
    obj.ccReqLogSplit(reqLogPath)
    print(obj.reqSplitList)
    uri = "http://www.test.com/2K.txt?test"
    header={"HOST":"www.test.com"}
    print obj.ccServerCheck(uri,header)
    obj.ccCleanReqLog()
    print(obj.reqSplitList)
    
#    d1 = None
#    print type({})==dict
#    print isinstance({},dict)
#    tup2 = (1, 2, 3, 4, 5 )
#    print tup2
#    print type(None)
#    print type(None) not in (types.DictType,types.ListType,types.TupleType,types.StringType,types.NoneType)
    #uri= 'http://www.test.com/cctesto'
    #checkHeaders = {"expect-Code":"404","Host":"www.test.com"}
    #print obj.ccServerCheck(uri, checkHeaders,ver="")


