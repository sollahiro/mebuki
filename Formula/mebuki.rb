class Mebuki < Formula
  desc "投資回避に特化した投資分析ツール"
  homepage "https://github.com/sollahiro/mebuki"
  url "https://github.com/sollahiro/mebuki/releases/download/v2.1.6/mebuki-macos-arm64.tar.gz"
  version "2.1.6"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # Updated by CI

  def install
    libexec.install Dir["mebuki/*"]
    bin.install_symlink libexec/"mebuki"
  end

  test do
    system "#{bin}/mebuki", "--version"
  end
end
