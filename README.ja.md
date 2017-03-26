# datadog-aws-ec2-count
AWS の EC2 のオンデマンドインスタンスの稼働状況を Datadog のカスタムメトリクスで取得するための Datadog プラグインです。

この Datadog プラグインで取得できる情報は以下になります。

- 稼働中の EC2 オンデマンドインスタンス数
- 有効な EC2 リザーブドインスタンス数
- 未使用状態の EC2 リザーブドインスタンス数
- 稼働中の EC2 インスタンス全数

この情報を利用することにより、リザーブドインスタンス契約の参考にしたり、無駄になっているリザーブドインスタンス契約を発見することができます。

これらの情報は AWS コンソールの EC2 レポートでも確認することができますが、この Datadog プラグインを用いることでリアルタイムかつ、時間ごとの利用状況を詳細に把握できるようになります。

# メトリクス一覧

| メトリクス名 | 内容 |
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
まず、Datadog プラグインをインストールするための、以下の EC2 インスタンスを用意します。

- Datadog Agent をインストール
- IAM Role で `ec2:DescribeInstances` 権限を付与

# インストール方法

# 制限事項
この Datadog プラグインには以下の制限事項があります。

- 
