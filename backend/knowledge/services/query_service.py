from typing import List
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from config.settings import settings

class QueryService:
    """检索服务"""

    def __init__(self):

        self.llm=ChatOpenAI(model_name=settings.MODEL,
                            openai_api_key=settings.API_KEY,
                            openai_api_base=settings.BASE_URL,
                            temperature=0) # temperature作用：控制模型输出的随机度 尽量不要让它乱发挥（尽最大努力保证：影响因素：硬件（并行gpu：精度变乱）网络（moe专家））



    def generate_answer(self, user_question:str, retrival_context: List[Document]) -> str:
        """
        对接大语言模型的入口
        Args:
            user_question: 用户问题
            retrival_context: 检索到的上下文

        Returns:
            str:LLM模型整合上下文之后的自然语言
        """

        # 1. 判断是否检索到了文档
        if not  retrival_context:
            return "未检索到任何相关的文档，无法提供回复"


        # 2. 处理检索到的知识内容
        retrival_context="\n\n".join([f"资料{index+1}:{document}"for index,document in enumerate(retrival_context)])

        # 3. 定义提示词
        prompt = f"""
        你是一位经验丰富的高级技术支持专家。请基于下方的【参考资料】回答【用户问题】。

         【参考资料】：
         ```
         {retrival_context}
         ```

         【用户问题】：
         ```
         {user_question}
         ```

         【回答要求】：
         1.  **基于事实**：严格基于【参考资料】的内容回答，严禁编造资料中未提及的信息。如果资料无法回答问题，请直接回答：“当前的知识库中暂时没有找到该问题的解决方案。”
         2.  **去特定化处理**：(重要)
             - 除非用户问题中明确指明了特定型号/品牌，否则在回答中请**移除**具体的设备型号、品牌名称（如“联想”、“K900”等）。
             - 例如：将“联想手机设置”泛化为“手机设置”；将“打开联想电脑管家”泛化为“打开系统管理软件”或“相关设置工具”。
         3.  **结构清晰**：
             - 如果是操作步骤，请使用有序列表（1. 2. 3.）。
             - 语言风格应简洁、专业、直接，避免寒暄和废话。
         4. 引用来源：在回答的最后，请列出你参考的【资料x】的编号(仅列出编号即可) 

         【开始回答】：
         """

        # 4. 调用模型
        llm_response=self.llm.invoke(prompt)


        # 5. 返回模型的结果
        return  llm_response.content





