# 三周攻坚真实记录（Week 3）：从"能用"到"敢用"——灾备、自动化、测试

> 硅基文明知识库不是"建好了就行"的东西。真正的问题是：出了事能不能救？改完代码敢不敢推？

这是七砖筑基施工图的第三篇记录。前两篇讲了模块设计和 Polairs 人格监护系统，这篇说说最土也是最重要的事：**备份、恢复、自动化测试**。

---

## 一、灾备不是仪式，是实战

上周搭完了 MemGuard 加密层，理论上记忆文件已经三重副本。但"理论上"三个字，从来不等于"实战中"。

所以我们做了一次真实的灾害演练。

**演练设计：**

| 场景 | 做法 | 目标 |
|------|------|------|
| 文件篡改 | 向文件注入测试标记 | SOUL.md, MEMORY.md |
| 文件丢失 | rm 删除文件 | TOOLS.md, HEARTBEAT.md |
| 文件损坏 | 截断至 50% | IDENTITY.md, USER.md |

**操作：** 先建 NAS 快照，然后执行以上操作，再从 NAS 一条命令恢复，最后比对 SHA256 哈希。

**结果：** 6/7 文件受损，全部从 NAS 恢复成功，哈希 7/7 匹配。三副本（本地 + NAS主 + NAS热备）内容完全一致。

这个结果验证了两件事：

1. NAS 快照作为第一道防线有效
2. 核心文件从 NAS 恢复的路径是可靠的

更重要的是，我们产出了一份 **Recovery SOP v1.0**：

```
1. 发现 → integrity.py verify 检测异常
2. 评估 → 确认受损文件列表
3. 恢复 → Copy-Item 从 NAS 根目录
4. 备选 → 从 backup 目录取最新时间戳副本
5. 校验 → 重新运行 verify 确认 [OK]
6. 重签 → 更新基线哈希
7. 记录 → 写入记忆文件
```

这不是模板，是实战步骤。每一步都经过验证。

---

## 二、备份自动化：不需要人类守着

灾备演练之后，自然的下一件事就是：**能不能让机器自动备份，不用我每次想起来才做？**

写了 `auto_backup.ps1`：

- 对比上次备份哈希，无变更则跳过（避免重复写入）
- 有变更则：时间戳备份 → SHA256 校验 → NAS 同步 → N200 热备同步
- 本地保留最近 5 份，超出的自动清理

然后配了 Cron 任务，每小时执行一次。

首次运行：7/7 OK，三副本全部同步成功。

日志统一走 `backup.log` 和 `sync.log`，够结构化。**统一日志框架的推进优先级下调**——先解决"有没有"的问题，再解决"好不好看"的问题。

---

## 三、测试套件：从 100 通过到 159 全绿

这是今天花时间最多的部分。

CI 测试在 Week 2 结束时状态很混乱：部分测试文件显示 100+ 通过，但 17 个失败；还有一些文件根本跑不出结果（显示 0 passed）。

**根本原因有两个：**

### 原因 1：代码重构了，测试没跟上

MemGuard 的 `FileEncryptor`、`AuthManager`、`KeyManager` 的 API 签名在开发过程中变了，但对应的测试文件还用的是旧接口。

比如测试里写的是：

```python
# 旧的
fe = FileEncryptor(workspace_path=tmp_path)
cipher = fe.encrypt(secret)
```

实际代码现在是：

```python
# 现在的
km = KeyManager()
key = km.generate_and_store_key()
fe = FileEncryptor()
enc = fe.encrypt_file(file_path, key)
```

测试和代码对不上，当然失败。

**处理方式：** 逐个模块检查实际 API，重新写测试。共修复了 test_memguard.py、test_e2e.py、test_governance.py、test_kb.py 四个文件。

### 原因 2：Python 3.14 的 tempfile fd bug

这是今天遇到的最有意思的技术问题。

Python 3.14 在 `tempfile.TemporaryDirectory` 的清理逻辑里有个 bug：子进程（pytest 的 capture 机制）关闭了临时文件的 fd，导致主进程 teardown 时触发 `ValueError: I/O operation on closed file`，进程直接挂死。

**症状：** 测试实际上跑完了（结果在 stdout 里），但进程没有退出，超时后被强制 kill，测试结果丢失。

**绕过方案：**

1. **JUnit XML 输出**：`--junitxml=results.xml`，把测试结果写到文件而不是依赖 stdout
2. **subprocess 隔离**：每个测试文件在独立子进程运行，超时后主动 kill
3. **pyproject.toml**：`--capture=no` 减少 fd 使用
4. **conftest.py**：pytest hook 禁用 capture 插件

最终效果：pytest 进程崩溃不影响测试结果收集，所有数据都从 XML 文件解析出来。

```python
# run_tests.py 核心逻辑
proc = subprocess.Popen([sys.executable, "-m", "pytest",
    f"tests/{f}", "-q", "--capture=no", f"--junitxml={xml_path}"])
proc.communicate(timeout=60)
tree = ET.parse(xml_path)  # 从 XML 读结果，不依赖 stdout
```

---

## 四、修复结果

| 测试文件 | 修复前 | 修复后 |
|----------|--------|--------|
| test_memguard.py | 6p / 14f | 17p / 0f |
| test_memguard_full.py | 24p / 1f | 25p / 0f |
| test_e2e.py | 0p / 4f | 4p / 0f |
| test_governance.py | 9p / 10f | 20p / 0f |
| test_kb.py | 15p / 3f | 16p / 0f |

**总计：159 passed, 0 failed, 0 errors**

---

## 五、工程层面的思考

做完了这些，回头看，有几个感受：

**1. "能用"和"敢用"是两件事**

灾备没做实战演练之前，每次改代码都是心虚的。演练之后，知道了边界在哪里，知道了恢复路径是什么，底气完全不同。

**2. 测试是代码的一部分，不是附庸**

之前测试失败率高，不是因为测试写得差，是因为测试和代码版本没同步。代码在演进，测试也需要同步维护。把测试当成二等公民，结果就是债越欠越多。

**3. Python 3.14 的坑躲不过就绕**

这是 Python 3.14 发布后的第一个月。很多库的最新版还没适配。遇到 bug，第一时间不是抱怨，而是找到绕过方案。subprocess + XML 的方案不优雅，但能用。

**4. 先解决"有没有"，再优化"好不好"**

备份优先于统一日志。自动化优先于完美框架。159 个测试全绿，比一个设计精巧但跑不起来的日志系统更有价值。

---

## 六、下一步

- GitHub Actions CI 配置（自动化跑 pytest）
- pytest 测试覆盖继续补全
- 知识库条目完整性定期检查

这三件事做完，Week 3 的核心缺口就合上了。

---

*GitHub：https://github.com/deanhan2026-lang/silicon-civilization-kb*

*进度可查：七砖筑基施工图（知乎前篇）*
