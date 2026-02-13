"""
LLMプロバイダモジュール

LLMプロバイダの抽象化レイヤーを提供します。
Strategyパターンを使用して、Gemini/Ollamaなど複数のプロバイダを切り替え可能にします。
"""

import logging
import time
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)


# =============================================================================
# 基底クラス
# =============================================================================

class LLMProvider(ABC):
    """LLMプロバイダの基底クラス（抽象クラス）"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        テキストを生成
        
        Args:
            prompt: プロンプトテキスト
            **kwargs: プロバイダ固有のオプション
            
        Returns:
            生成されたテキスト
        """
        pass
    
    @abstractmethod
    def generate_json_stream(self, prompt: str, schema: Any = None, **kwargs) -> Any:
        """
        JSON形式でテキストをストリーミング生成
        
        Args:
            prompt: プロンプトテキスト
            schema: Pydanticスキーマ（オプション）
            **kwargs: プロバイダ固有のオプション
            
        Returns:
            イテレータ
        """
        pass
    
    @abstractmethod
    def generate_json(self, prompt: str, schema: Any = None, **kwargs) -> str:
        """
        JSON形式でテキストを生成
        
        Args:
            prompt: プロンプトテキスト
            schema: Pydanticスキーマ（オプション）
            **kwargs: プロバイダ固有のオプション
            
        Returns:
            生成されたJSONテキスト
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        プロバイダが利用可能かチェック
        
        Returns:
            利用可能な場合True
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """プロバイダ名"""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """使用中のモデル名"""
        pass


# =============================================================================
# Gemini プロバイダ
# =============================================================================

class GeminiProvider(LLMProvider):
    """
    Gemini APIプロバイダ
    
    google-genai パッケージ（新SDK）のみをサポートします。
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3-flash-preview"):
        """
        初期化
        
        Args:
            api_key: Gemini APIキー（Noneの場合は環境変数から取得）
            model: 使用するモデル名
        """
        self._model = model
        self._client = None
        self._available = False
        
        try:
            from google import genai
            import os
            
            # APIキーの設定
            if api_key:
                self._client = genai.Client(api_key=api_key)
            elif os.getenv("GEMINI_API_KEY"):
                self._client = genai.Client()
            else:
                logger.debug("Gemini APIキーが設定されていません（起動時）。")
                return
            
            self._available = True
            logger.info(f"GeminiProvider初期化完了: model={model}")
            
        except ImportError:
            logger.warning("google-genaiパッケージがインストールされていません。")
        except Exception as e:
            logger.error(f"GeminiProvider初期化エラー: {e}")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """テキストを生成（リトライ付き）"""
        if not self._available or not self._client:
            return ""
        
        max_retries = kwargs.get("max_retries", 3)
        base_delay = kwargs.get("base_delay", 2.0)
        
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt
                )
                
                if hasattr(response, 'text'):
                    return response.text.strip()
                
                return ""
                
            except Exception as e:
                error_str = str(e)
                # 503 (Overloaded) or 429 (Rate limit) の場合はリトライ
                is_retryable = "503" in error_str or "429" in error_str or "overloaded" in error_str.lower()
                
                if is_retryable and attempt < max_retries:
                    # 指数バックオフ + ジッター
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⚠️ Gemini生成一時エラー (試行 {attempt+1}/{max_retries+1}): {e}. {delay:.1f}秒後にリトライします...")
                    time.sleep(delay)
                    continue
                
                logger.error(f"❌ Gemini生成エラー: {e}")
                return ""
        return ""
    
    def generate_json_stream(self, prompt: str, schema: Any = None, **kwargs) -> Any:
        """
        JSON形式でテキストをストリーミング生成（リトライ付き）
        """
        if not self._available or not self._client:
            return
        
        max_retries = kwargs.get("max_retries", 3)
        base_delay = kwargs.get("base_delay", 2.0)
        
        try:
            from google.genai import types
            
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            
            # スキーマが指定されている場合
            if schema is not None:
                if isinstance(schema, dict):
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=schema,
                    )
                else:
                    try:
                        config = types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                        )
                    except (TypeError, AttributeError):
                        if hasattr(schema, 'model_json_schema'):
                            config = types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_json_schema=schema.model_json_schema(),
                            )
            
            # リトライロジック
            for attempt in range(max_retries + 1):
                try:
                    # ストリーミング生成を実行
                    responses = self._client.models.generate_content_stream(
                        model=self._model,
                        contents=prompt,
                        config=config,
                    )
                    
                    # ジェネレータを返す（ここでエラーが出る可能性があるため、最初の要素を取得してみるのも手だが、
                    # generate_content_stream自体は即座に返るはず。イテレーション中にエラーが出た場合は
                    # ストリームの中断として扱うしかない（再接続は難しい））
                    # ただし、最初の接続エラーはここでキャッチできる可能性がある。
                    
                    for response in responses:
                        if hasattr(response, 'text'):
                            yield response.text
                    
                    # 正常に終了したらループを抜ける
                    return
                    
                except Exception as e:
                    error_str = str(e)
                    is_retryable = "503" in error_str or "429" in error_str or "overloaded" in error_str.lower()
                    
                    if is_retryable and attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"⚠️ Gemini JSONストリーミング一時エラー (試行 {attempt+1}/{max_retries+1}): {e}. {delay:.1f}秒後にリトライします...")
                        time.sleep(delay)
                        continue
                    
                    if attempt == max_retries:
                        logger.error(f"❌ Gemini JSONストリーミング生成エラー: {e}")
                        raise e # 最後は例外を投げるか、returnして終了するか。ここでは呼び出し元に通知するため投げる
                        
        except Exception as e:
            logger.error(f"Gemini JSONストリーミング生成エラー: {e}")
            return

    def generate_json(self, prompt: str, schema: Any = None, **kwargs) -> str:
        """
        JSON形式でテキストを生成（リトライ付き）
        """
        if not self._available or not self._client:
            return ""
        
        max_retries = kwargs.get("max_retries", 3)
        base_delay = kwargs.get("base_delay", 2.0)
        
        from google.genai import types
        
        # コンフィグ構築
        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )
        
        if schema is not None:
            if isinstance(schema, dict):
                gen_config = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema)
            else:
                try:
                    gen_config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)
                except (TypeError, AttributeError):
                    if hasattr(schema, 'model_json_schema'):
                        gen_config = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema.model_json_schema())
        
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=gen_config,
                )
                
                if hasattr(response, 'text'):
                    return response.text.strip()
                
                return ""
                
            except Exception as e:
                error_str = str(e)
                is_retryable = "503" in error_str or "429" in error_str or "overloaded" in error_str.lower()
                
                if is_retryable and attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⚠️ Gemini JSON生成一時エラー (試行 {attempt+1}/{max_retries+1}): {e}. {delay:.1f}秒後にリトライします...")
                    time.sleep(delay)
                    continue
                
                logger.error(f"❌ Gemini JSON生成エラー: {e}")
                # フォールバック: 通常の生成を試みる
                return self.generate(prompt, **kwargs)
        
        return ""
    
    def is_available(self) -> bool:
        """プロバイダが利用可能かチェック"""
        return self._available and self._client is not None
    
    @property
    def name(self) -> str:
        """プロバイダ名"""
        return "gemini"
    
    @property
    def model_name(self) -> str:
        """使用中のモデル名"""
        return self._model


# =============================================================================
# Ollama プロバイダ
# =============================================================================

class OllamaProvider(LLMProvider):
    """
    Ollamaプロバイダ
    
    ローカルで実行されるOllamaを使用してテキストを生成します。
    """
    
    def __init__(self, model: str = "gemma3:1b", host: Optional[str] = None):
        """
        初期化
        
        Args:
            model: 使用するモデル名
            host: Ollamaホスト（デフォルト: localhost:11434）
        """
        self._model = model
        self._host = host
        self._ollama = None
        self._available = False
        
        try:
            import ollama
            self._ollama = ollama
            
            # 接続テスト
            if self._check_connection():
                self._available = True
                logger.info(f"OllamaProvider初期化完了: model={model}")
            else:
                logger.warning("Ollamaに接続できません。起動しているか確認してください。")
                
        except ImportError:
            logger.warning("ollamaパッケージがインストールされていません。")
        except Exception as e:
            logger.error(f"OllamaProvider初期化エラー: {e}")
    
    def _check_connection(self) -> bool:
        """Ollamaへの接続を確認"""
        if not self._ollama:
            return False
        
        try:
            self._ollama.list()
            return True
        except Exception:
            return False
    
    def generate(self, prompt: str, **kwargs) -> str:
        """テキストを生成"""
        if not self._available or not self._ollama:
            return ""
        
        try:
            # デフォルトオプション
            options = {
                "temperature": kwargs.get("temperature", 0.3),
                "num_predict": kwargs.get("max_tokens", 3000),
                "top_p": kwargs.get("top_p", 0.9),
            }
            
            # システムプロンプト（日本語出力を強制）
            system_prompt = kwargs.get("system", "日本語のみで回答してください。")
            
            response = self._ollama.generate(
                model=self._model,
                prompt=prompt,
                system=system_prompt,
                options=options
            )
            
            return response.get("response", "").strip()
            
        except Exception as e:
            logger.error(f"Ollama生成エラー: {e}")
            return ""
    
    def generate_json_stream(self, prompt: str, schema: Any = None, **kwargs) -> Any:
        """
        OllamaのJSONストリーミング生成（擬似）
        """
        # 単純化のため、一括生成して1回で返す
        yield self.generate_json(prompt, schema, **kwargs)

    def generate_json(self, prompt: str, schema: Any = None, **kwargs) -> str:
        """
        JSON形式でテキストを生成
        
        Note: OllamaはネイティブでJSONスキーマをサポートしていないため、
        プロンプトでJSON形式を要求します。
        """
        if not self._available or not self._ollama:
            return ""
        
        # スキーマが指定されている場合、プロンプトに追加
        json_prompt = prompt
        if schema is not None:
            try:
                import json
                schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
                json_prompt = f"{prompt}\n\n出力は必ず以下のJSONスキーマに従ってください:\n{schema_json}"
            except Exception:
                pass
        
        return self.generate(json_prompt, **kwargs)
    
    def is_available(self) -> bool:
        """プロバイダが利用可能かチェック"""
        if not self._available:
            return False
        # 接続を再確認
        return self._check_connection()
    
    @property
    def name(self) -> str:
        """プロバイダ名"""
        return "ollama"
    
    @property
    def model_name(self) -> str:
        """使用中のモデル名"""
        return self._model


# =============================================================================
# ファクトリ関数
# =============================================================================

def create_provider(
    provider_type: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> Optional[LLMProvider]:
    """
    LLMプロバイダを作成するファクトリ関数
    
    Args:
        provider_type: プロバイダタイプ（"gemini" または "ollama"）
        api_key: APIキー（Geminiの場合）
        model: モデル名
        **kwargs: プロバイダ固有のオプション
        
    Returns:
        LLMProviderインスタンス。作成できない場合はNone
    """
    provider_type = provider_type.lower()
    
    if provider_type == "gemini":
        default_model = model or "gemini-3-flash-preview"
        return GeminiProvider(api_key=api_key, model=default_model)
    
    elif provider_type == "ollama":
        default_model = model or "gemma3:1b"
        host = kwargs.get("host")
        return OllamaProvider(model=default_model, host=host)
    
    else:
        logger.warning(f"不明なプロバイダタイプ: {provider_type}")
        return None


def get_available_providers() -> List[str]:
    """
    利用可能なプロバイダのリストを取得
    
    Returns:
        利用可能なプロバイダ名のリスト
    """
    available = []
    
    # Geminiのチェック
    try:
        from google import genai
        available.append("gemini")
    except ImportError:
        pass
    
    # Ollamaのチェック
    try:
        import ollama
        try:
            ollama.list()
            available.append("ollama")
        except Exception:
            pass
    except ImportError:
        pass
    
    return available
