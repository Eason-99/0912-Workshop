# Workshop PPT 生成说明

当前版本严格沿用 `plan.md` 的 S0–S7：S0 API、S1 Structured Output、S2 Tools、S3 Workflow、S4 Agent Loop、S5 State、S6 Planning、S7 Reflection。

主讲部分共 22 页。每个 Stage 固定使用两页：第一页在同一套六列坐标中累计增加系统模块，并标出对应源码；第二页固定回答“当前输出、仍缺什么、下一阶段为何必要”。最后附 4 页备用材料。

## 生成方式

在项目根目录执行：

```bash
python PPT/generate_workshop_ppt.py
```

脚本会生成：

- `agent_from_scratch_workshop.pptx`：26 页演示文稿，其中 22 页为主讲、4 页为备用。
- `speaker_notes.md`：不进入 PPT 画布的逐页讲者备注。
- `previews/slide_XX.png`：由同一组页面对象生成的布局预览。
- `qa_report.json`：越界、重叠和可能文字溢出的确定性检查结果。
- `rendered/`：系统存在 LibreOffice 与 `pdftoppm` 时生成的真实 PPT 渲染结果。

## 依赖

```bash
python -m pip install -r PPT/requirements.txt
```

脚本使用 `python-pptx` 创建可编辑原生对象，使用 Pillow 生成检查预览。若安装了 LibreOffice 与 `pdftoppm`，脚本会自动执行真实 PPTX → PDF → PNG 渲染；缺少时会在质量报告中明确记录降级，不会伪造渲染成功。

布局、主题、页脚、Stage 进度条和讲者备注均由脚本统一生成。需要调整叙事时，优先修改脚本中的 `V2_STAGES` 数据表；架构页和输出页会同步更新。

## 可替换素材

以下素材不是外部图库图片，而是 Demo 运行后产生的项目素材。文件不存在时，PPT 会保留带文件名的可编辑占位框：

- `assets/s0_draft_excerpt.png`
- `assets/s2_events.png`
- `assets/s2_deck_preview.png`
- `assets/s4_trace.png`
- `assets/s4_result_slide.png`
- `assets/s7_before.png`
- `assets/s7_after.png`

将素材放入对应路径后重新运行脚本即可自动替换占位框。

`assets/NotoSansCJKsc-Regular.otf` 仅供 PNG 预览正确显示中文，不会被作为图片或整页背景写入 PPT。
