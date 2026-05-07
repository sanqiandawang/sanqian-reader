#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

echo "   ◇━━━━━━━━━━━━━━━━━━━━━◇"
echo "   │    三 千 要 看      │"
echo "   ◇━━━━━━━━━━━━━━━━━━━━━◇"
echo ""
echo "   正在启动..."
echo ""

python server.py &
sleep 2

# 自动打开浏览器
open "http://localhost:8765"

echo "   ✅ 已启动！"
echo "   浏览器访问: http://localhost:8765"
echo "   Kindle 访问: http://$(ipconfig getifaddr en0 2>/dev/null || echo '你的Mac IP'):8765"
echo ""
echo "   关闭此窗口不会停止服务。"
echo "   按 Control+C 可停止服务。"
echo ""

# 等待，让用户可以看到信息
wait
