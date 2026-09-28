"""Runtime local de PaddleOCR. Protocolo JSONL, sin ejecución de texto del PDF."""
import contextlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['OMP_NUM_THREADS'] = '6'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PADDLE_PDX_CACHE_HOME'] = str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SINCAL' / 'ocr-cache')


def emit(result):
    print('SINCAL_OCR:' + json.dumps(result, ensure_ascii=True), flush=True)


def main():
    ocr = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                if ocr is None:
                    from paddleocr import PaddleOCR
                    ocr = PaddleOCR(
                        device='cpu', cpu_threads=6, enable_mkldnn=False,
                        use_doc_orientation_classify=False, use_doc_unwarping=False,
                        use_textline_orientation=False, text_rec_score_thresh=0.0,
                        text_detection_model_name='PP-OCRv6_medium_det',
                        text_recognition_model_name='PP-OCRv6_medium_rec',
                        text_detection_model_dir=str(ROOT / 'models' / 'PP-OCRv6_medium_det'),
                        text_recognition_model_dir=str(ROOT / 'models' / 'PP-OCRv6_medium_rec'))
                result = list(ocr.predict(request['image']))[0].json
                result = result.get('res', result)
            emit({key: result[key] for key in ('rec_texts', 'rec_scores', 'rec_boxes')})
        except Exception as error:
            emit({'error': f'{type(error).__name__}: {error}'})


if __name__ == '__main__':
    main()
