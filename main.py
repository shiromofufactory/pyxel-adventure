from dotenv import load_dotenv
import pyxel
import openai
import json
import os

load_dotenv()
openai.api_key = os.environ["OPENAI_APIKEY"]  # OpenAIのAPIキーを.envから読み込む

MODE_GM = 0
MODE_ACTION = 1
MODE_END = 2

# 日本語フォント表示（Pyxel公式サンプル 13_bitmap_font.py より）
class BDFRenderer:
    BORDER_DIRECTIONS = [
        (-1, -1),
        (0, -1),
        (1, -1),
        (-1, 0),
        (1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
    ]

    def __init__(self, bdf_filename):
        self.fonts = self._parse_bdf(bdf_filename)
        self.screen_ptr = pyxel.screen.data_ptr()
        self.screen_width = pyxel.width

    def _parse_bdf(self, bdf_filename):
        fonts = {}
        code = None
        bitmap = None
        with open(bdf_filename, "r") as f:
            for line in f:
                if line.startswith("ENCODING"):
                    code = int(line.split()[1])
                elif line.startswith("BBX"):
                    bbx_data = list(map(int, line.split()[1:]))
                    font_width, font_height = bbx_data[0], bbx_data[1]
                elif line.startswith("BITMAP"):
                    bitmap = []
                elif line.startswith("ENDCHAR"):
                    fonts[code] = (font_width, font_height, bitmap)
                    bitmap = None
                elif bitmap is not None:
                    hex_string = line.strip()
                    bin_string = bin(int(hex_string, 16))[2:].zfill(len(hex_string) * 4)
                    bitmap.append(int(bin_string[::-1], 2))
        return fonts

    def _draw_font(self, x, y, font, color):
        font_width, font_height, bitmap = font
        screen_ptr = self.screen_ptr
        screen_width = self.screen_width
        for j in range(font_height):
            for i in range(font_width):
                if (bitmap[j] >> i) & 1:
                    screen_ptr[(y + j) * screen_width + x + i] = color

    def draw_text(self, x, y, text, color=7, border_color=None):
        for char in text:
            code = ord(char)
            if code not in self.fonts:
                continue
            font = self.fonts[code]
            if border_color is not None:
                for dx, dy in self.BORDER_DIRECTIONS:
                    self._draw_font(
                        x + dx,
                        y + dy,
                        font,
                        border_color,
                    )
            self._draw_font(x, y, font, color)
            x += font[0] + 1


# メインクラス
class App:
    def __init__(self):
        pyxel.init(256, 256, title="Pyxel Adventure")
        pyxel.load("./asset.pyxres")
        self.size_x = 22
        self.size_y = 16
        self.texts = []
        self.mode = MODE_GM
        self.bdf = BDFRenderer("umplus_j10r.bdf")
        # チャットメッセージ準備
        self.chat_messages = [
            {
                "role": "user",
                "content": """
                    今からテーブルトークRPGをします。あなたはゲームマスターの役割を果たしてください。

                    ## 舞台設定
                    * プレイヤーの男性（私）は、相棒の女性「ミク」とともに、洞窟の奥深くにある秘宝を探しに行きます。
                    * ミクは楽天的な性格で、くだけた口調で喋ります。
                    * 洞窟には危険な生物が生息しており、また多くの罠が潜んでいます。

                    ## ゲームのルール
                    * あなたは状況を説明し、私に行動の選択肢を最大4つ提示してください。私は数字で行動を選択します。
                    * 道中にはさまざまハプニングが発生します。
                    * 私とミクが秘宝を見つけて洞窟の外に持ち帰れば、私の勝ちです。もし、秘宝を見つけられずに洞窟から撤退するか、2人のうちどちらかが大怪我をすると、私の負けです。

                    それでは、ゲームを始めてください。
                """,
            },
        ]
        # BGM読み込み
        with open(f"bgm1.json", "rt") as fin:
            self.bgm1 = json.loads(fin.read())
        with open(f"bgm2.json", "rt") as fin:
            self.bgm2 = json.loads(fin.read())
        # メイン処理実行
        self.play(self.bgm1)
        pyxel.run(self.update, self.draw)

    def draw(self):
        pyxel.cls(0)
        pyxel.blt(0, 0, 0, 0, 0, 256, 256)
        for y in range(min(self.size_y, len(self.texts))):
            self.bdf.draw_text(2, 16 + y * 14, self.texts[y], 7, 0)

    def update(self):
        if self.mode == MODE_GM:
            answer = self.generate_answer()
            self.texts = []
            self.add_text(answer)
            # GMのメッセージに「おめでとう」が入っていたらクリアとみなす
            if "おめでとう" in answer:
                self.play(self.bgm2)
                self.end_game()
            # それ以外＆選択肢の数字がなければゲームオーバーとみなす
            elif not "1" in answer:
                self.end_game()
            else:
                self.mode = MODE_ACTION
        elif self.mode == MODE_ACTION:
            if pyxel.btnp(pyxel.KEY_1):
                prompt = "1"
            elif pyxel.btnp(pyxel.KEY_2):
                prompt = "2"
            elif pyxel.btnp(pyxel.KEY_3):
                prompt = "3"
            elif pyxel.btnp(pyxel.KEY_4):
                prompt = "4"
            else:
                return
            self.add_text("\n私の行動：" + prompt)
            self.chat_messages.append({"role": "user", "content": prompt})
            self.mode = MODE_GM

    # ゲーム終了
    def end_game(self):
        self.add_text("\n[Esc]でゲームを終了します。")
        self.mode = MODE_END

    # BGM再生
    def play(self, bgm):
        for ch, sound in enumerate(bgm):
            pyxel.sound(ch).set(*sound)
            pyxel.play(ch, ch, loop=True)

    # 画面にテキスト追加
    def add_text(self, words):
        self.texts.append("")
        for word in words:
            if len(self.texts) > self.size_y:
                self.texts.pop(0)
            idx = len(self.texts) - 1
            if word == "\n":
                self.texts.append("")
            else:
                if not word in ["。", "、"] and len(self.texts[idx]) >= self.size_x:
                    self.texts.append("")
                    idx += 1
                self.texts[idx] += word

    # チャットメッセージ生成
    def generate_answer(self):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=self.chat_messages,
            temperature=0.6,
            frequency_penalty=1.0,
        )
        answer = response["choices"][0]["message"]["content"]
        self.chat_messages.append({"role": "assistant", "content": answer})
        return answer


App()
