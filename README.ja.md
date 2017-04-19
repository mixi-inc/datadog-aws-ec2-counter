[![Build Status](https://travis-ci.org/mounemoi/datadog-aws-ec2-counter.svg?branch=master)](https://travis-ci.org/mounemoi/datadog-aws-ec2-counter)

# datadog-aws-ec2-counter
AWS の EC2 のオンデマンドインスタンスの稼働状況を Datadog のカスタムメトリクスで取得するための Datadog Agent Check です。

この Agent Check で取得できる情報は以下になります。

- 稼働中の EC2 オンデマンドインスタンス数と footprint 値
- 有効な EC2 リザーブドインスタンス数と footprint 値
- 未使用状態の EC2 リザーブドインスタンス数と footprint 値
- 稼働中の EC2 インスタンス全数と footprint 値

この情報を利用することにより、リザーブドインスタンスの契約の参考にしたり、無駄になっているリザーブドインスタンス契約を発見することができます。

これらの情報は AWS コンソールの EC2 レポートでも確認することができますが、この Agent Check を用いることでリアルタイムかつ、時間ごとの利用状況を詳細に把握できるようになります。

# メトリクス一覧

この Agent Check で取得されるメトリクス一覧は以下となります。

| メトリクス | 内容 |
|-|-|
| aws_ec2_count.ondemand.count | 稼働中の EC2 オンデマンドインスタンス数 |
| aws_ec2_count.ondemand.footprint | 稼働中の EC2 オンデマンドインスタンスの footprint 値 |
| aws_ec2_count.reserved.count | 有効な EC2 リザーブドインスタンス数 |
| aws_ec2_count.reserved.footprint | 有効な EC2 リザーブドインスタンスの footprint 値 |
| aws_ec2_count.reserved_unused.count | 未使用状態の EC2 リザーブドインスタンス数 |
| aws_ec2_count.reserved_unused.footprint | 未使用状態の EC2 リザーブドインスタンスの footprint 値 |
| aws_ec2_count.running.count | 稼働中の EC2 インスタンス数 |
| aws_ec2_count.running.footprint | 稼働中の EC2 インスタンスの footprint 値 |

各メトリクスには以下のタグが付けられており、どの Availability Zone か Instance Type かを判別できるようになっています。

| Tag | 内容 |
|-|-|
| ac-az | Availability Zone (Region RI の場合は '') |
| ac-family | Instance Family |
| ac-type | Instance Type |

# 用意するもの

以下の EC2 インスタンスを用意します。

- Datadog Agent をインストール
- IAM Role で `ec2:DescribeInstances` 権限を付与

このインスタンスに、この Agent Check をインストールします。

# インストール方法

ここでは、CentOS にインストールした Datadog Agent に、この Agent Check をインストールする方法を記載します。
インストール環境によって適宜読み替えてください。

## 1. AWS SDK のインストール

Agent Check から [AWS SDK for Python](https://aws.amazon.com/jp/sdk-for-python/) が利用できるようにインストールを行います。

```bash
$ sudo /opt/datadog-agent/embedded/bin/pip install boto3
```

## 2. カスタム Check のインストール
このリポジトリの `checks.d/aws_ec2_count.py` を `/etc/dd-agent/checks.d/` に配置します。

```bash
$ sudo cp ./checks.d/aws_ec2_count.py /etc/dd-agent/checks.d/
```

## 3. カスタム Check の設定ファイルの配置
このリポジトリの `conf.d/aws_ec2_count.yaml.example` を参考に、 `/etc/dd-agent/conf.d/aws_ec2_count.yaml` を作成します。

```yaml:aws_ec2_count.yaml
init_config:
    min_collection_interval: 60

instances:
    - region: 'ap-northeast-1'
```

- min_collection_interval にはチェック間隔（秒数）を指定します
- region には、チェックを行うリージョンを記述します。複数リージョンを取得するには instances に配列で指定します。

取得対象が東京リージョンであれば、この `aws_ec2_count.yaml.example` をそのまま利用すれば良いでしょう。

```bash
$ sudo cp conf.d/aws_ec2_count.yaml.example /etc/dd-agent/conf.d/aws_ec2_count.yaml
```

## 4. Datadog Agent の再起動
以上で Agent Check のインストールは完了です。
最後に Datadog Agent を再起動します。

```bash
$ sudo /etc/init.d/datadog-agent restart
```

これで、Datadog にカスタムメトリクスが送信されているはずです。

# 制限事項
この Agent Check には以下の制限事項があります。

- オンデマンドインスタンス数は、稼働中のインスタンスと有効なリザーブドインスタンス数との差分で求めています
    - このため、請求額と完全に一致しない場合があります
    - また、 今後の AWS 側の仕様変更などにより、リザーブドインスタンスの適用条件が変わる可能性があります
- Region RI は以下の条件で適用するように計算しています
    - Instance Type が一致しているものに優先的に適用
    - 余剰分は同一 Instance Family の最小の Instanence Size から適用するようにしています
        - これにより、オンデマンドインスタンス数が最小になるようにしています
- リザーブドインスタンスの変更時に、タイミングによってはリザーブドインスタンス数を正常に取得できない時があります
- 以下のインスタンスにのみ対応しています
    - プラットフォームが Linux/UNIX のもの
    - テナンシーが デフォルト のもの

