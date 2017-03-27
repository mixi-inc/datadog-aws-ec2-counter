# datadog-aws-ec2-count
AWS の EC2 のオンデマンドインスタンスの稼働状況を Datadog のカスタムメトリクスで取得するための Datadog カスタム Check です。

この Datadog カスタム Check で取得できる情報は以下になります。

- 稼働中の EC2 オンデマンドインスタンス数
- 有効な EC2 リザーブドインスタンス数
- 未使用状態の EC2 リザーブドインスタンス数
- 稼働中の EC2 インスタンス全数

この情報を利用することにより、リザーブドインスタンスの契約の参考にしたり、無駄になっているリザーブドインスタンス契約を発見することができます。

これらの情報は AWS コンソールの EC2 レポートでも確認することができますが、この Datadog カスタム Check を用いることでリアルタイムかつ、時間ごとの利用状況を詳細に把握できるようになります。

# メトリクス一覧

このカスタム Check で取得されるメトリクス一覧は以下となります。

| メトリクス | 内容 |
|-|-|
| aws_ec2_count.ondemand.count | 稼働中の EC2 オンデマンドインスタンス数 |
| aws_ec2_count.reserved.count | 有効な EC2 リザーブドインスタンス数 |
| aws_ec2_count.reserved.unused | 未使用状態の EC2 リザーブドインスタンス数 |
| aws_ec2_count.running.count | 稼働中の EC2 インスタンス数 |

各メトリクスには以下のタグが付けられており、どの AZ かインスタンスタイプかを判別できるようになっています。

| Tag | 内容 |
|-|-|
| ac-availability-zone | Availability Zone |
| ac-instance-type | インスタンスタイプ |

# 用意するもの

以下の EC2 インスタンスを用意します。

- Datadog Agent をインストール
- IAM Role で `ec2:DescribeInstances` 権限を付与

このインスタンスに、この Datadog プラグインをインストールします。

# インストール方法

ここでは、CentOS にインストールした Datadog Agent に、このプラグインをインストールする方法を記載します。
インストール環境によって適宜読み替えてください。

## 1. AWS SDK のインストール

Datadog プラグインから [AWS SDK for Python](https://aws.amazon.com/jp/sdk-for-python/) が利用できるようにインストールを行います。

```bash
$ sudo /opt/datadog-agent/embedded/bin/pip install boto3
```

## 2. カスタム Check のインストール
このリポジトリの `checks.d/aws-ec2-count.py` を `/etc/dd-agent/checks.d/` に配置します。

```bash
$ sudo cp ./checks.d/aws-ec2-count.py /etc/dd-agent/checks.d/
```

## 3. カスタム Check の設定ファイルの配置
このリポジトリの `conf.d/aws-ec2-count.yaml.example` を参考に、 `/etc/dd-agent/conf.d/aws-ec2-count.yaml` を作成します。

```yaml:aws-ec2-count.yaml
init_config:
    min_collection_interval: 60

instances:
    - region: 'ap-northeast-1'
```

- min_collection_interval にはチェック間隔（秒数）を指定します
- region には、チェックを行うリージョンを記述します。複数リージョンを取得するには instances に配列で指定します。

取得対象が東京リージョンであれば、この `aws-ec2-count.yaml.example` をそのまま利用すれば良いでしょう。

```bash
$ sudo cp conf.d/aws-ec2-count.yaml.example /etc/dd-agent/conf.d/aws-ec2-count.yaml
```

## 4. Datadog Agent の再起動
以上でカスタム Check のインストールは完了です。
最後に Datadog Agent を再起動します。

```bash
$ sudo /etc/init.d/datadog-agent restart
```

これで、Datadog にカスタムメトリクスが送信されているはずです。

# 制限事項
このカスタム Check には以下の制限事項があります。

- オンデマンドインスタンス数は、稼働中のインスタンスと有効なリザーブドインスタンス数との差分で求めています
  - なので、請求額と完全に一致しない場合があります
- 以下のリザーブドインスタンスにのみ対応しています
  - プラットフォームが Linux/UNIX のもの
  - テナンシーが デフォルト のもの
  - AvailabilityZone 指定のもの （Region指定のものには対応していません）
