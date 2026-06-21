# 🌐 Git 网络急救

> GitHub 连接失败、push/pull 超时、代理问题。

---

## 症状速查

| 症状 | 诊断 | 修复 |
|:-----|:-----|:------|
| `Recv failure: Connection was reset` | 网络不稳定 / DNS 污染 | ① DNS 刷新 ② 重试 |
| `Could not connect to server` | DNS 解析失败 / 代理干扰 | ① DNS 刷新 ② 代理排查 ③ 换源 |
| `Failed to connect to github.com port 443` | 防火墙 / VPN / 代理 | ① 关 VPN ② 清代理 ③ 检查 hosts |
| `SSL certificate problem` | 证书过期 / 时间不准 | 同步系统时间 / `git config --global http.sslverify false` |
| 开了加速器/VPN 仍然连不上 | 代理端口未自动配置给 Git | ② 扫描加速器代理端口 |

---

## 修复步骤

### ① 清 DNS 缓存

```bash
# Windows
ipconfig /flushdns

# macOS
sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder

# Linux
sudo systemctl-resolve flush-caches  # systemd-resolved
sudo service nscd restart            # nscd
```

### ② 检测加速器/VPN 代理端口

开加速器或 VPN 后系统环境变量不一定自动设，Git 可能不知道走代理。扫描常见端口：

```bash
# 扫描常用代理端口（clash/SSR/v2ray 默认端口范围）
for port in $(seq 1080 1090) $(seq 7890 7899) $(seq 8080 8090); do
  code=$(curl -s --connect-timeout 1 -o /dev/null -w "%{http_code}" \
    -x http://127.0.0.1:$port https://github.com 2>/dev/null)
  if [ "$code" != "000" ] && [ -n "$code" ]; then
    echo "  ✓ port $port → HTTP $code"
    break
  fi
done
```

找到后配置 Git 使用该端口：

```bash
git config --global http.proxy http://127.0.0.1:7892
git config --global https.proxy http://127.0.0.1:7892
# 推送完成后关闭加速器时清除：
# git config --global --unset http.proxy
# git config --global --unset https.proxy
```

> **关闭加速器后务必清除**，否则 Git 会一直走代理导致直连失败。

### ③ 清 Git 代理

```bash
# 查看当前代理
git config --global --get http.proxy
git config --global --get https.proxy

# 清除代理
git config --global --unset http.proxy
git config --global --unset https.proxy

# 清除系统环境变量代理（Windows PowerShell）
[System.Environment]::SetEnvironmentVariable("HTTP_PROXY", $null, "User")
[System.Environment]::SetEnvironmentVariable("HTTPS_PROXY", $null, "User")
```

### ④ 验证连通性

```bash
# DNS 解析是否正常
nslookup github.com
# 正常应返回 20.205.243.166

# 直连测试
curl -s --max-time 10 https://github.com -o /dev/null -w "%{http_code}"
# 返回 200 说明网络通

# 如果 DNS 返回了奇怪 IP（如 172.x.x.x），说明走的是内网 DNS，
# 可能是公司网络/VPN 接管了 DNS
```

### ⑤ 使用 SSH 替代 HTTPS

```bash
# 检查现有 remote
git remote -v

# 切换为 SSH
git remote set-url origin git@github.com:NoahLightryyy/litchi-head.git

# 如果 SSH key 没配置
ssh-keygen -t ed25519 -C "your_email@example.com"
# 公钥添加到 GitHub: Settings → SSH and GPG keys
```

### ⑥ 国内网络备选方案

```bash
# 如果 GitHub 间歇性无法访问，用 Gitee 镜像作为 backup remote
git remote add gitee https://gitee.com/your-username/litchi-head.git
git push gitee main
```

---

## 经验教训

- 问题根源通常在 **DNS 污染**（公司内网 / ISP），而非 GitHub 宕机
- `Connection was reset` 往往是**间歇性的**，等 30s 重试可能就通了
- 如果 `nslookup` 返回的是 172.16.x.x（内网地址），说明 DNS 被内网劫持
- 清 DNS 加清代理两步做完基本能解决 90% 问题
- **开了加速器/VPN 仍连不上，先扫描代理端口（步骤 ②），而非先清代理** — 你的加速器可能给了端口但没配给 Git
- 加速器代理端口通常用 `seq 7890 7899` 或 `seq 1080 1090` 能找到
