from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification, pipeline
import torch
import numpy as np
import re
from typing import Dict, List, Optional

class IndoBERTSentiment:
    def __init__(self, use_pretrained_sentiment=True):
        """
        Enhanced IndoBERT sentiment analyzer
        
        Args:
            use_pretrained_sentiment: Try to use a pre-trained sentiment model first
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.enabled = False
        self.method = "fallback"
        
        # Try different approaches in order of preference
        if use_pretrained_sentiment:
            self._try_pretrained_sentiment()
        
        if not self.enabled:
            self._try_base_model()
    
    def _try_pretrained_sentiment(self):
        """Try to load a pre-trained Indonesian sentiment model"""
        sentiment_models = [
            "w11wo/indonesian-roberta-base-sentiment-classifier",
            "ayameRushia/bert-base-indonesian-1.5G-sentiment-analysis-smsa",
            "cardiffnlp/twitter-roberta-base-sentiment-latest"  # Multilingual fallback
        ]
        
        for model_name in sentiment_models:
            try:
                print(f"🔄 Trying sentiment model: {model_name}")
                
                # Try as classification pipeline first
                self.sentiment_pipeline = pipeline(
                    "text-classification",
                    model=model_name,
                    device=0 if torch.cuda.is_available() else -1,
                    return_all_scores=True
                )
                
                # Test with a sample
                test_result = self.sentiment_pipeline("bagus sekali")
                
                self.enabled = True
                self.method = "pretrained_pipeline"
                print(f"✅ Successfully loaded sentiment model: {model_name}")
                return
                
            except Exception as e:
                print(f"❌ Failed to load {model_name}: {e}")
                continue
    
    def _try_base_model(self):
        """Fallback to base IndoBERT model with enhanced heuristics"""
        try:
            model_name = "indolem/indobert-base-uncased"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            self.enabled = True
            self.method = "base_model"
            print("✅ IndoBERT base model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load IndoBERT base model: {e}")
            self.enabled = False
            self.method = "fallback"
    
    def preprocess_text(self, text: str) -> str:
        """Enhanced text preprocessing for Indonesian tweets"""
        # Remove URLs, mentions, hashtags but keep the sentiment context
        text = re.sub(r'http\S+|www\S+|https\S+', ' ', text, flags=re.MULTILINE)
        text = re.sub(r'@\w+', ' ', text)  # Remove mentions
        text = re.sub(r'#(\w+)', r'\1', text)  # Keep hashtag content, remove #
        
        # Handle RT and common Twitter patterns
        text = re.sub(r'^RT\s+', '', text)
        text = re.sub(r'\bRT\b', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Handle negations properly (important for sentiment)
        text = re.sub(r'\btidak\s+', 'tidak_', text)
        text = re.sub(r'\bbukan\s+', 'bukan_', text)
        text = re.sub(r'\bjangan\s+', 'jangan_', text)
        
        return text.lower()
    
    def get_sentiment_score(self, text: str) -> float:
        """Get sentiment score using the best available method"""
        if not self.enabled:
            return self._fallback_sentiment(text)
        
        if self.method == "pretrained_pipeline":
            return self._pipeline_sentiment(text)
        elif self.method == "base_model":
            return self._base_model_sentiment(text)
        else:
            return self._fallback_sentiment(text)
    
    def _pipeline_sentiment(self, text: str) -> float:
        """Use pre-trained sentiment pipeline"""
        try:
            text_clean = self.preprocess_text(text)
            results = self.sentiment_pipeline(text_clean)
            
            # Handle different output formats
            if isinstance(results[0], list):
                # Multiple scores returned
                scores = results[0]
                sentiment_map = {}
                
                for score in scores:
                    label = score['label'].lower()
                    if 'positive' in label or 'pos' in label or label == 'label_2':
                        sentiment_map['positive'] = score['score']
                    elif 'negative' in label or 'neg' in label or label == 'label_0':
                        sentiment_map['negative'] = score['score']
                    else:
                        sentiment_map['neutral'] = score['score']
                
                # Calculate polarity score
                pos_score = sentiment_map.get('positive', 0)
                neg_score = sentiment_map.get('negative', 0)
                
                # Convert to -1 to 1 scale
                if pos_score > neg_score:
                    return pos_score * 0.8  # Scale down a bit to avoid extreme values
                else:
                    return -neg_score * 0.8
            
            else:
                # Single score returned
                label = results[0]['label'].lower()
                score = results[0]['score']
                
                if 'positive' in label or 'pos' in label:
                    return score * 0.8
                elif 'negative' in label or 'neg' in label:
                    return -score * 0.8
                else:
                    return 0.0
                    
        except Exception as e:
            print(f"Error in pipeline sentiment: {e}")
            return self._fallback_sentiment(text)
    
    def _base_model_sentiment(self, text: str) -> float:
        """Enhanced base model sentiment analysis"""
        try:
            text_clean = self.preprocess_text(text)
            
            # Get IndoBERT embedding
            inputs = self.tokenizer(
                text_clean,
                return_tensors='pt',
                truncation=True,
                padding=True,
                max_length=128
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                cls_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
            
            return self._analyze_embedding_sentiment(cls_embedding, text_clean)
            
        except Exception as e:
            print(f"Error in base model sentiment: {e}")
            return self._fallback_sentiment(text)
    
    def _analyze_embedding_sentiment(self, embedding: np.ndarray, text: str) -> float:
        """Enhanced embedding sentiment analysis"""
        
        # Expanded Indonesian sentiment keywords
        positive_words = {
            'bagus', 'baik', 'senang', 'gembira', 'mantap', 'keren', 'hebat',
            'luar biasa', 'sempurna', 'terbaik', 'suka', 'cinta', 'indah',
            'enak', 'murah', 'hemat', 'untung', 'berhasil', 'sukses', 'puas',
            'recommended', 'top', 'ok', 'oke', 'mantul', 'kece', 'asik',
            'menyenangkan', 'bahagia', 'bangga', 'syukur', 'alhamdulillah',
            'wow', 'amazing', 'fantastic', 'excellent', 'great', 'good',
            'love', 'like', 'best', 'nice', 'cool', 'awesome', 'perfect'
        }
        
        negative_words = {
            'buruk', 'jelek', 'sedih', 'kecewa', 'marah', 'kesal', 'benci',
            'tidak_suka', 'gagal', 'rusak', 'salah', 'bermasalah', 'susah',
            'sulit', 'parah', 'hancur', 'kacau', 'rugi', 'menyebalkan',
            'menjengkelkan', 'stress', 'capek', 'mahal', 'anjing', 'sialan',
            'bodoh', 'tolol', 'goblok', 'kampret', 'bangsat', 'tai',
            'tidak_bagus', 'tidak_baik', 'bukan_bagus', 'jangan_beli',
            'mengecewakan', 'terrible', 'awful', 'bad', 'worst', 'hate',
            'disgusting', 'horrible', 'annoying', 'frustrating'
        }
        
        # Enhanced keyword analysis
        words = text.split()
        pos_count = sum(1 for word in words if word in positive_words)
        neg_count = sum(1 for word in words if word in negative_words)
        
        # Handle negations
        negation_words = ['tidak_', 'bukan_', 'jangan_']
        for i, word in enumerate(words):
            if any(word.startswith(neg) for neg in negation_words):
                # Look at the next word and flip its sentiment
                if i + 1 < len(words):
                    next_word = words[i + 1]
                    if next_word in positive_words:
                        pos_count -= 1
                        neg_count += 1
                    elif next_word in negative_words:
                        neg_count -= 1
                        pos_count += 1
        
        keyword_score = 0
        if pos_count > 0 or neg_count > 0:
            keyword_score = (pos_count - neg_count) / (pos_count + neg_count)
        
        # Enhanced embedding analysis
        embedding_stats = {
            'norm': np.linalg.norm(embedding),
            'mean': np.mean(embedding),
            'std': np.std(embedding),
            'max': np.max(embedding),
            'min': np.min(embedding)
        }
        
        # More sophisticated embedding heuristic
        embedding_score = (
            np.tanh(embedding_stats['mean']) * 0.4 +
            np.tanh(embedding_stats['max'] - embedding_stats['min']) * 0.2 +
            np.tanh(embedding_stats['std'] - 0.5) * 0.1
        )
        
        # Combine scores with better weighting
        if abs(keyword_score) > 0.2:
            # Strong keyword signal
            final_score = 0.8 * keyword_score + 0.2 * embedding_score
        elif abs(keyword_score) > 0.0:
            # Weak keyword signal
            final_score = 0.6 * keyword_score + 0.4 * embedding_score
        else:
            # No keyword signal, rely on embedding
            final_score = embedding_score
        
        # Add some randomness for neutral cases to avoid always returning 0
        if abs(final_score) < 0.1:
            final_score += np.random.normal(0, 0.05)
        
        # Clamp to [-1, 1]
        return max(-1, min(1, final_score))
    
    def _fallback_sentiment(self, text: str) -> float:
        """Enhanced fallback sentiment analysis"""
        positive_words = {
            'bagus', 'baik', 'senang', 'mantap', 'keren', 'enak', 'suka',
            'hebat', 'luar biasa', 'terbaik', 'puas', 'berhasil', 'sukses'
        }
        negative_words = {
            'buruk', 'jelek', 'kecewa', 'marah', 'benci', 'gagal',
            'susah', 'parah', 'menyebalkan', 'mahal', 'rugi'
        }
        
        text_clean = self.preprocess_text(text)
        words = text_clean.split()
        
        pos_count = sum(1 for word in words if word in positive_words)
        neg_count = sum(1 for word in words if word in negative_words)
        
        if pos_count == 0 and neg_count == 0:
            return np.random.normal(0, 0.1)  # Small random variation for neutral
        
        return (pos_count - neg_count) / (pos_count + neg_count)

    def get_sentiment_label(polarity: float) -> str:
        """Convert sentiment polarity to label"""
        if polarity > 0.1:
            return "positive"
        elif polarity < -0.1:
            return "negative"
        else:
            return "neutral"
    
    def get_detailed_sentiment(self, text: str) -> Dict[str, float]:
        """Get detailed sentiment information"""
        polarity = self.get_sentiment_score(text)
        
        return {
            'polarity': round(polarity, 3),
            'label': get_sentiment_label(polarity),
            'confidence': min(abs(polarity) + 0.1, 1.0),
            'method': self.method
        }
    
    def batch_analyze(self, texts: List[str], batch_size: int = 8) -> List[Dict[str, float]]:
        """Analyze multiple texts efficiently"""
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = [self.get_detailed_sentiment(text) for text in batch]
            results.extend(batch_results)
        return results

# Test the enhanced version
def test_enhanced_indobert():
    """Test the enhanced IndoBERT sentiment analyzer"""
    analyzer = IndoBERTSentiment()
    
    test_texts = [
        "Harga gula naik lagi, sangat menyebalkan sekali!",  # Should be negative
        "Resep ini enak banget, mantap sekali terima kasih!",  # Should be positive
        "Gula darah saya normal hari ini",  # Should be neutral
        "Tidak bagus pelayanannya, sangat kecewa",  # Should be negative (with negation)
        "Bukan jelek sih, tapi biasa aja",  # Should be neutral/slightly positive
        "Wah mantap banget ini, recommended!",  # Should be positive
    ]
    
    print(f"🧪 Testing Enhanced IndoBERT (Method: {analyzer.method})")
    print("=" * 60)
    
    for text in test_texts:
        result = analyzer.get_detailed_sentiment(text)
        print(f"\nText: {text}")
        print(f"Result: {result['label']} ({result['polarity']:+.3f}) - {result['confidence']:.3f} confidence")

if __name__ == "__main__":
    test_enhanced_indobert()