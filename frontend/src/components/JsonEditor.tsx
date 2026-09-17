import { useRef } from 'react';

interface JsonEditorProps {
  value: string;
  onChange: (v: string) => void;
}

/**
 * JSON 编辑区：多行文本直接编辑 + 文件选择上传。上传仅把文件内容读入
 * 文本框，真正的整批校验发生在后端，避免前后端规则不一致。
 */
export function JsonEditor({ value, onChange }: JsonEditorProps) {
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    const text = await file.text();
    onChange(text);
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>输入 JSON</h2>
        <div className="panel-actions">
          <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
            上传 JSON
          </button>
          <button
            type="button"
            className="btn ghost"
            onClick={() => {
              try {
                onChange(JSON.stringify(JSON.parse(value), null, 2));
              } catch {
                /* 当前不是合法 JSON，忽略格式化 */
              }
            }}
            title="规范化缩进当前 JSON"
          >
            格式化
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json,application/text"
            style={{ display: 'none' }}
            onChange={(e) => {
              void handleFile(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
        </div>
      </div>
      <textarea
        className="json-editor"
        spellCheck={false}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="审查输入 JSON 编辑器"
      />
    </section>
  );
}
