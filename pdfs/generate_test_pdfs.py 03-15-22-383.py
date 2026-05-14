"""
Generate Test PDFs for Multi-Speaker Audiobook Testing
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

def create_harry_potter_test():
    """Create Harry Potter dialogue test PDF"""
    filename = "test_harry_potter.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Content
    content = """
<b>The Mysterious Letter</b>

Harry Potter sat in his small bedroom at the Dursleys' house, staring out the window. The morning was bright and sunny, but Harry felt troubled. Strange things had been happening lately, and he couldn't shake the feeling that something important was about to occur.

Suddenly, there was a knock at the door. Hermione burst into the room, her face flushed with excitement.

"Harry, you won't believe what I found!" she exclaimed, waving a piece of parchment.

"What is it?" Harry asked, sitting up quickly.

"It's a letter from Dumbledore," Hermione said breathlessly. "He wants to see us immediately. He says it's urgent!"

Harry felt his heart racing. Whenever Dumbledore sent urgent messages, it usually meant trouble was brewing.

"Did Ron get one too?" Harry asked.

"Yes," Hermione replied. "He's waiting downstairs. We need to go now!"

Harry grabbed his wand and followed Hermione down the stairs. Ron was standing by the door, looking nervous.

"This is serious, isn't it?" Ron said quietly.

"I think so," Harry replied. "But we'll face it together, like always."

The three friends exchanged determined looks and headed out the door.
"""
    
    # Add content
    story.append(Paragraph(content, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    print(f"✅ Created: {filename}")
    return filename


def create_conversation_test():
    """Create simple conversation test PDF"""
    filename = "test_conversation.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    content = """
<b>A Coffee Shop Conversation</b>

Sarah walked into the busy coffee shop and spotted her friend Mike sitting at a corner table.

"Hey Mike! Sorry I'm late," Sarah said, sliding into the seat across from him.

"No worries," Mike replied with a smile. "I just got here myself. How have you been?"

"Busy as always," Sarah sighed. "Work has been crazy this month."

"I know the feeling," Mike said. "My boss just assigned me three new projects."

The barista called out Sarah's name. She went to pick up her latte and returned to the table.

"So, what did you want to talk about?" Sarah asked.

"I'm thinking about moving to New York," Mike said nervously. "I got a job offer there."

Sarah's eyes widened. "Wow, that's huge! Are you going to take it?"

"I'm not sure yet," Mike admitted. "It's a great opportunity, but it means leaving everyone here."

"Well," Sarah said thoughtfully, "you should do what's best for your career. We'll always be friends, no matter where you are."

Mike smiled gratefully. "Thanks, Sarah. That means a lot."
"""
    
    story.append(Paragraph(content, styles['Normal']))
    doc.build(story)
    print(f"✅ Created: {filename}")
    return filename


def create_multilingual_test():
    """Create PDF with English and Urdu content"""
    filename = "test_multilingual.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Add Urdu-compatible style
    urdu_style = ParagraphStyle(
        'Urdu',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=20,
    )
    
    english_content = """
<b>English Section - Customer Service</b>

The customer called the helpline, frustrated with the service.

"I've been waiting for three hours," the customer complained. "This is unacceptable!"

"I sincerely apologize for the inconvenience," the agent responded calmly. "Let me help you resolve this issue right away."

"I hope so," the customer said. "I've called twice already."

"I understand your frustration," the agent said. "I'm looking at your account now and I can see the problem."
"""
    
    urdu_content = """
<b>اردو حصہ - کسٹمر سروس</b>

ہماری ہیلپ لائن تمام حکومتی سہولیات، درخواستیں، شکایات اور معلومات فراہم کرنے کے لیے موجود ہے۔

آپ کے سوال اور مسئلے کی نوعیت جاننے کے بعد، میں آپ کو مرحلہ وار رہنمائی فراہم کروں گی۔

اگر آپ تیار ہیں تو برائے کرم اپنا سوال اور خدمت کا موضوع بیان کریں۔
"""
    
    story.append(Paragraph(english_content, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(urdu_content, urdu_style))
    
    doc.build(story)
    print(f"✅ Created: {filename}")
    return filename


def create_short_test():
    """Create very short test PDF (for quick testing)"""
    filename = "test_short.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    content = """
<b>Quick Test Story</b>

Emma found a mysterious box in her attic.

"What is this?" Emma wondered aloud.

Her brother Tom came upstairs.

"Did you find something?" Tom asked.

"Yes, look at this old box," Emma said excitedly.

Tom examined it carefully. "It looks ancient!"
"""
    
    story.append(Paragraph(content, styles['Normal']))
    doc.build(story)
    print(f"✅ Created: {filename}")
    return filename


def create_fairy_tale_test():
    """Create fairy tale test PDF with multiple characters"""
    filename = "test_fairy_tale.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    content = """
<b>The Three Friends and the Dragon</b>

Once upon a time, in a peaceful village, there lived three brave friends: Alice, Bob, and Charlie. One day, they heard terrible news.

"A dragon has been spotted near the forest!" the town crier announced.

"We must do something," Alice said with determination.

"But we're just kids," Bob said nervously. "How can we fight a dragon?"

"Maybe we don't need to fight it," Charlie suggested. "Maybe we can talk to it."

The three friends ventured into the forest. Soon, they found the dragon sleeping under a large oak tree.

"Hello, Mr. Dragon," Alice called out bravely.

The dragon opened one eye. "Why do you disturb my sleep?" he grumbled.

"We heard you were scaring the villagers," Bob said.

"I'm not trying to scare anyone," the dragon said sadly. "I'm just lonely. No one wants to be friends with a dragon."

"We'll be your friends!" Charlie exclaimed.

The dragon's eyes lit up. "Really? You would be friends with me?"

"Of course," Alice said kindly. "Everyone deserves friendship."

From that day on, the dragon protected the village, and the three friends visited him every day. They all lived happily ever after.
"""
    
    story.append(Paragraph(content, styles['Normal']))
    doc.build(story)
    print(f"✅ Created: {filename}")
    return filename


if __name__ == "__main__":
    print("=" * 60)
    print("Generating Test PDFs...")
    print("=" * 60)
    
    create_short_test()
    create_harry_potter_test()
    create_conversation_test()
    create_fairy_tale_test()
    create_multilingual_test()
    
    print("=" * 60)
    print("✅ All test PDFs created!")
    print("=" * 60)
