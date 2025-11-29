import re

path = '/echo?message=helloworlddfljasd_lkdsaf aklfjdLKSF'
check = re.findall("[=](.+)", path)
content = check[0]
print(content)
print(type(content))