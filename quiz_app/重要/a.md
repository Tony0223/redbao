soul@tony quiz_app % keytool -genkeypair \
-alias quiz \
-keyalg RSA \
-keysize 2048 \
-validity 36500 \
-keystore release.keystore
输入密钥库口令:  Tony@2026App
再次输入新口令:  Tony@2026App
您的名字与姓氏是什么?
  [Unknown]:  Tony
您的组织单位名称是什么?
  [Unknown]:  Personal
您的组织名称是什么?
  [Unknown]:  Tony Studio
您所在的城市或区域名称是什么?
  [Unknown]:  beijing
您所在的省/市/自治区名称是什么?
  [Unknown]:  beijing
该单位的双字母国家/地区代码是什么?
  [Unknown]:  CN
CN=Tony, OU=Personal, O=Tony Studio, L=beijing, ST=beijing, C=CN是否正确?
  [否]:  yes
您的名字与姓氏是什么?
  [Tony]:  
您的组织单位名称是什么?
  [Personal]:  
您的组织名称是什么?
  [Tony Studio]:  
您所在的城市或区域名称是什么?
  [beijing]:  
您所在的省/市/自治区名称是什么?
  [beijing]:  
该单位的双字母国家/地区代码是什么?
  [CN]:  
CN=Tony, OU=Personal, O=Tony Studio, L=beijing, ST=beijing, C=CN是否正确?
  [否]:  
您的名字与姓氏是什么?
  [Tony]:  
您的组织单位名称是什么?
  [Personal]:  
您的组织名称是什么?
  [Tony Studio]:  
您所在的城市或区域名称是什么?
  [beijing]:  
您所在的省/市/自治区名称是什么?
  [beijing]:  
该单位的双字母国家/地区代码是什么?
  [CN]:  
CN=Tony, OU=Personal, O=Tony Studio, L=beijing, ST=beijing, C=CN是否正确?
  [否]:  y

输入 <quiz> 的密钥口令
	(如果和密钥库口令相同, 按回车):  

Warning:
JKS 密钥库使用专用格式。建议使用 "keytool -importkeystore -srckeystore release.keystore -destkeystore release.keystore -deststoretype pkcs12" 迁移到行业标准格式 PKCS12。
soul@tony quiz_app % 
soul@tony quiz_app % 
soul@tony quiz_app % 
soul@tony quiz_app % ls -l release.keystore
-rw-r--r--  1 soul  staff  2236  7 30 09:30 release.keystore


查看证书信息  keytool -list -v -keystore release.keystore

查看MD5值  /Users/soul/Library/Android/sdk/build-tools/37.0.0/apksigner verify --print-certs __UNI__F320E8E__20260804115045.apk

导出证书
keytool -exportcert \
-alias quiz \
-keystore release.keystore \
-rfc \
-file cert.pem

查看公钥
openssl x509 -pubkey -noout -in cert.pem


---- 
DCloud 应用离线Key: fd02789d4d4df07c67165632d2938cb4
appid: __UNI__F320E8E

SHA1: DB:8A:BA:18:EA:53:60:D0:B5:92:C9:E0:A1:D6:05:C7:5E:A6:EF:FD



MD5 digest: 84cb9d380b7becd8e4857bf170ede861

SHA-256 digest: f88a72fc52b11f553508b56375c028d70b46c0e8a8334d879377c9cb684c7400

SHA-1 digest: db8aba18ea5360d0b592c9e0a1d605c75ea6effd

公钥
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAgOPCRuFfNksem1MZfbec
6ki09L1AxOntlCcC0ClsEpxscuRZWN8mJ/BkyZGvEN5qvfNMjeRll9wvC/YrwWTu
VZdFvCf7erVyQPq3dm4g+BHVZ5GZwgjaZwCibnLkcpBp0ATfqNV/9PZ1V0l37NyI
LHJaeq4ZCQdp8RKZpI+V2wz/aFP/NQ5j35SSQINXz6orBPfLQENDqKnqU49ovVGO
zvjZr8dHDN0+zBuu7ExWKY7llGxPL77Z9Lr3E4Gzx6DmjfWR85quxWPbB66X3Ab9
vIpv4J0TM64foYpRiRxYEeYdHaIhbZ4j8i+ZarhAU/uflozegh/NSBJ/Y2TlIWS2
hwIDAQAB
-----END PUBLIC KEY-----


