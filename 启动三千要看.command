#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

clear
cat << 'EOF'

         ／l、
       （ﾟ､ ｡ ７     三千正在为你读长文...
         l  ~ヽ        📖
         じしf_,)ノ

   ◇━━━━━━━━━━━━━━━━━━━━◇
   │     三 千 要 看      │
   ◇━━━━━━━━━━━━━━━━━━━━◇

EOF

echo "   正在启动..."
echo ""

python server.py &
sleep 2

open "http://localhost:8765"

echo ""
echo "   ✅ 已启动！"
echo "   浏览器: http://localhost:8765"
echo "   Kindle:  http://$(ipconfig getifaddr en0 2>/dev/null || echo '你的Mac IP'):8765"
echo ""
echo "   关闭此窗口不会停止服务"
echo "   按 Control+C 停止服务"
echo ""

wait
