"""ChromaDB Viewer - Streamlit 기반 데이터 뷰어

사용법:
    streamlit run tools/chroma_viewer/viewer.py
    # .env 파일이나 AWS 설정 없이도 로컬 DB만 있으면 작동합니다.
"""

import os

import chromadb
import streamlit as st

# 프로젝트 루트 경로 (ai/ 디렉토리) 계산
# tests/utils/chroma_viewer/viewer.py -> tests/utils/chroma_viewer -> tests/utils -> tests -> ai
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

# 설정 하드코딩 (Config 의존성 제거)
CHROMA_PERSIST_DIR = os.path.join(project_root, "chroma_data")
CHROMA_COLLECTION_NAME = "interactions"


def main():
    st.set_page_config(
        page_title="ChromaDB Viewer",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 ChromaDB Viewer")
    st.markdown(f"**Database Path:** `{CHROMA_PERSIST_DIR}`")
    st.markdown(f"**Collection:** `{CHROMA_COLLECTION_NAME}`")
    st.divider()

    try:
        # ChromaDB 직접 연결 (Server/Bedrock 의존성 제거)
        if not os.path.exists(CHROMA_PERSIST_DIR):
            st.error(f"❌ 데이터 폴더를 찾을 수 없습니다: {CHROMA_PERSIST_DIR}")
            return

        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

        try:
            collection = client.get_collection(CHROMA_COLLECTION_NAME)
        except Exception:
            # 컬렉션이 없을 경우
            st.warning(f"⚠️ '{CHROMA_COLLECTION_NAME}' 컬렉션이 존재하지 않습니다.")
            st.info("💡 `tools/seed_chromadb.py`를 실행해서 데이터를 생성해주세요.")
            return

        # 전체 데이터 조회
        result = collection.get()

        if not result or not result["ids"]:
            st.warning("⚠️ 데이터가 없습니다!")
            return

        count = len(result["ids"])
        st.success(f"✅ 총 **{count}개** 문서 발견")

        # 사이드바 필터
        st.sidebar.header("🔎 필터")
        search_query = st.sidebar.text_input("Document ID 검색", "")

        # 필터링 (간단한 검색)
        filtered_indices = []
        ids = result["ids"]
        for i in range(count):
            if not search_query or search_query.lower() in ids[i].lower():
                filtered_indices.append(i)

        st.sidebar.info(f"필터링된 문서: {len(filtered_indices)}개")

        # 데이터 표시
        for idx in filtered_indices:
            doc_id = result["ids"][idx]
            metadata = result["metadatas"][idx] if result["metadatas"] else {}
            document = result["documents"][idx] if result["documents"] else ""

            with st.expander(f"📄 {doc_id}", expanded=False):
                col1, col2 = st.columns([1, 2])

                with col1:
                    st.subheader("📋 Metadata")
                    if metadata:
                        for key, value in metadata.items():
                            st.text(f"{key}: {value}")
                    else:
                        st.text("(없음)")

                with col2:
                    st.subheader("📝 Document")
                    st.text_area(
                        "Content",
                        value=document,
                        height=200,
                        key=f"doc_{idx}",
                        disabled=True,
                    )

    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        import traceback

        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
