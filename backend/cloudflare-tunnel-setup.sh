#!/bin/bash
# Cloudflare Tunnel Setup (Free SSL without domain!)

echo "🌐 Installing Cloudflare Tunnel..."

# Install cloudflared
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
rm cloudflared-linux-amd64.deb

echo "✅ Cloudflared installed!"
echo ""
echo "📝 Next steps:"
echo "1. Login to Cloudflare:"
echo "   cloudflared tunnel login"
echo ""
echo "2. Create a tunnel:"
echo "   cloudflared tunnel create doc-matcher-api"
echo ""
echo "3. Route traffic:"
echo "   cloudflared tunnel route dns doc-matcher-api api.yourname.cloudflare.com"
echo ""
echo "4. Start the tunnel:"
echo "   cloudflared tunnel run --url http://localhost:8000 doc-matcher-api"
echo ""
echo "You'll get a free *.trycloudflare.com URL with HTTPS!"
