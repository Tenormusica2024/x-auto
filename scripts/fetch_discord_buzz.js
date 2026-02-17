/**
 * Discord #en-buzz-tweets チャンネルから最新メッセージを取得するワンショットスクリプト
 *
 * 用途: discourse-freshness-updater から呼び出し、英語バズツイートの最新バッチを取得
 *
 * 使い方:
 *   node fetch_discord_buzz.js                   # 直近50件取得→JSON出力
 *   node fetch_discord_buzz.js --limit 100       # 件数指定
 *   node fetch_discord_buzz.js --hours 168       # 直近168時間（1週間）
 *   node fetch_discord_buzz.js --output file     # ファイル出力（data/discord-buzz-latest.json）
 *
 * 前提: DISCORD_BOT_TOKEN 環境変数が設定されていること
 *       Bot がサーバーに参加済みで、チャンネル読み取り権限があること
 */

const { Client, GatewayIntentBits } = require('discord.js');

// 設定
const CHANNEL_ID = '1473225110063415316'; // #en-buzz-tweets
const DEFAULT_LIMIT = 50;
const DEFAULT_HOURS = 168; // 1週間

// 引数パース
const args = process.argv.slice(2);
const getArg = (flag) => {
  const idx = args.indexOf(flag);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
};

const limit = parseInt(getArg('--limit') || DEFAULT_LIMIT);
const hours = parseInt(getArg('--hours') || DEFAULT_HOURS);
const outputMode = getArg('--output') || 'stdout'; // stdout or file

// Bot Token確認
const TOKEN = process.env.DISCORD_BOT_TOKEN;
if (!TOKEN) {
  console.error(JSON.stringify({
    error: 'DISCORD_BOT_TOKEN environment variable is not set',
    hint: 'Set it via: setx DISCORD_BOT_TOKEN "your_token_here"'
  }));
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent
  ]
});

client.once('ready', async () => {
  try {
    const channel = await client.channels.fetch(CHANNEL_ID);
    if (!channel) {
      throw new Error(`Channel ${CHANNEL_ID} not found`);
    }

    // メッセージ取得（Discord APIは1回100件まで）
    let allMessages = [];
    let lastId = null;
    const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000);

    while (allMessages.length < limit) {
      const fetchLimit = Math.min(100, limit - allMessages.length);
      const options = { limit: fetchLimit };
      if (lastId) options.before = lastId;

      const messages = await channel.messages.fetch(options);
      if (messages.size === 0) break;

      for (const [id, msg] of messages) {
        if (msg.createdAt < cutoff) {
          // 時間範囲外に到達
          lastId = null;
          break;
        }
        allMessages.push(msg);
        lastId = id;
      }

      if (!lastId) break; // 時間範囲外またはメッセージ終了
    }

    // Captain Hookメッセージをパース
    // 形式: @username (xxxxL): [日本語要約]\n元ツイートURL
    const parsed = allMessages.map(msg => {
      const content = msg.content;
      const lines = content.split('\n').filter(l => l.trim());

      // Like数の抽出: (1234L) パターン
      const likeMatch = content.match(/\((\d+(?:,\d+)?)L\)/);
      const likes = likeMatch ? parseInt(likeMatch[1].replace(',', '')) : 0;

      // ユーザー名の抽出: @username パターン
      const userMatch = content.match(/@(\w+)/);
      const username = userMatch ? `@${userMatch[1]}` : 'unknown';

      // 要約の抽出: ): の後から次の行まで
      const summaryMatch = content.match(/\):\s*(.+)/);
      const summary = summaryMatch ? summaryMatch[1].trim() : content.substring(0, 100);

      // URLの抽出
      const urlMatch = content.match(/(https?:\/\/(?:x\.com|twitter\.com)\/\S+)/);
      const url = urlMatch ? urlMatch[1] : null;

      return {
        discord_message_id: msg.id,
        timestamp: msg.createdAt.toISOString(),
        username,
        likes,
        summary,
        url,
        raw_content: content
      };
    });

    const result = {
      fetched_at: new Date().toISOString(),
      channel_id: CHANNEL_ID,
      message_count: parsed.length,
      hours_range: hours,
      messages: parsed.sort((a, b) => b.likes - a.likes) // Like数降順
    };

    if (outputMode === 'file') {
      const fs = require('fs');
      const outPath = require('path').join(__dirname, 'data', 'discord-buzz-latest.json');
      fs.writeFileSync(outPath, JSON.stringify(result, null, 2), 'utf8');
      console.error(`Saved ${parsed.length} messages to ${outPath}`);
    }

    // stdoutにはJSON出力（claude -p から読めるように）
    console.log(JSON.stringify(result, null, 2));

  } catch (err) {
    console.error(JSON.stringify({ error: err.message }));
    process.exit(1);
  } finally {
    client.destroy();
    process.exit(0);
  }
});

client.login(TOKEN);
