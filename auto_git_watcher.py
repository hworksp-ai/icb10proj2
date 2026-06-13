"""
자동 Git 동기화 스크립트 (auto_git_watcher.py)

이 스크립트는 프로젝트 디렉터리를 모니터링하여 파일 변경 사항(생성, 수정, 삭제)이 감지되면
자동으로 'git add', 'git commit', 'git push'를 순차적으로 실행해 줍니다.
무한 루프 방지를 위해 '.git', '.venv', '__pycache__' 등의 경로는 무시하며,
파일 저장이 빈번하게 일어날 때 연속적으로 실행되는 것을 방지하기 위해 디바운싱(Debounce) 기법을 적용했습니다.
"""

import os
import sys
import time
import subprocess
from threading import Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 감시할 타겟 경로 (현재 스크립트 위치 기준 루트 경로)
WATCH_PATH = os.path.dirname(os.path.abspath(__file__))

# 무시할 경로 및 파일 확장자 정의
IGNORE_DIRS = [".git", ".venv", "__pycache__", ".agents", ".claude"]
IGNORE_EXTENSIONS = [".pyc", ".pyo", ".tmp", ".log", ".lock"]

class GitSyncHandler(FileSystemEventHandler):
    def __init__(self, debounce_delay=2.0):
        super().__init__()
        self.debounce_delay = debounce_delay
        self.timer = None

    def on_any_event(self, event):
        # 디렉터리 자체의 이벤트는 무시
        if event.is_directory:
            return

        # 무시할 폴더에 속해 있는지 체크
        path_parts = os.path.normpath(event.src_path).split(os.sep)
        if any(ignored in path_parts for ignored in IGNORE_DIRS):
            return

        # 무시할 파일 확장자 체크
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() in IGNORE_EXTENSIONS:
            return

        print(f"🔍 변경 감지됨: {event.event_type} - {event.src_path}")
        self.reset_timer()

    def reset_timer(self):
        # 기존 타이머가 있으면 취소
        if self.timer:
            self.timer.cancel()
        
        # 지정된 지연시간(초) 후에 실제 Git 푸시 명령을 실행하도록 타이머 설정
        self.timer = Timer(self.debounce_delay, self.run_git_sync)
        self.timer.start()

    def run_git_sync(self):
        print("\n🔄 자동 커밋 및 푸시 작업을 시작합니다...")
        try:
            # 1. git status 확인하여 실제 변경 사항이 존재하는지 검사
            status_check = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=WATCH_PATH,
                capture_output=True,
                text=True,
                check=True
            )
            
            # 변경 사항이 전혀 없는 경우 스킵
            if not status_check.stdout.strip():
                print("ℹ️ 실제 변경 사항이 없습니다. 작업을 스킵합니다.")
                return

            # 2. git add 실행
            print("📦 git add . 진행 중...")
            subprocess.run(["git", "add", "-A"], cwd=WATCH_PATH, check=True)

            # 3. git commit 실행
            commit_msg = f"auto: 변경 사항 자동 반영 ({time.strftime('%Y-%m-%d %H:%M:%S')})"
            print(f"📝 git commit -m '{commit_msg}' 진행 중...")
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=WATCH_PATH, check=True)

            # 4. git push 실행
            print("🚀 git push origin main 진행 중...")
            subprocess.run(["git", "push", "origin", "main"], cwd=WATCH_PATH, check=True)

            print("✅ 자동 커밋 및 원격 저장소 푸시 완료!")

        except subprocess.CalledProcessError as e:
            print(f"❌ Git 작업 중 오류 발생: {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ 예기치 못한 에러 발생: {e}", file=sys.stderr)


if __name__ == "__main__":
    print(f"▶️ Git 자동 동기화 감시를 시작합니다. (감시 경로: {WATCH_PATH})")
    print("중단하려면 Ctrl+C를 누르세요.")
    
    event_handler = GitSyncHandler(debounce_delay=3.0)  # 파일 저장 종료 후 3초 대기
    observer = Observer()
    observer.schedule(event_handler, WATCH_PATH, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️ 감시를 중단합니다.")
        observer.stop()
    observer.join()
