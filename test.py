from dotenv import load_dotenv
import asyncio
load_dotenv()

from engine.edi_converter import EDIConverter


edi_converter = EDIConverter()

text = """This is a summary of a transaction set with the identifier code 810 and control number 7540. The transaction occurred on Wednesday, 6th March 2024, and is linked to an invoice numbered 0090033194, dated Tuesday, 27th February 2024. The associated purchase order number is 5331450317. 

The internal vendor number for reference identification is 434291920. The transaction involves shipping to Walmart DC 7017G General, which can be located using the global location number (GLN) 0078742042220. The address is 843 State Route 43 in Wintersville, Ohio, with the postal code 439527099.

The supplier or manufacturer involved is Winland Foods Inc, based at PO Box 735382 in Chicago, Illinois. The postal code for this location is 606735363. 

The terms of this transaction offer a basic discount. This is based on the invoice date, with terms of 2% discount due by Thursday, 28th March 2024 (22 days due). The net is due on Wednesday, 10th April 2024 (35 days net). The discount amount offered is $578.7. The terms are described as 2% 22 Net 35 (EFT).

The shipment was made on Wednesday, 6th March 2024, through a method of payment described as collect. The shipping point is described as Ex Works. 

The assigned identification for the invoiced quantity is 001, and the quantity invoiced is 390 cases, each priced at $17.14. The buyer's item number for the product or service is 009219918. 

The product is described as a 12/12oz Pasta Shell Jumbo - GVRL, packaged in packs of 12.Here is the rewritten information:

1.⁠ ⁠Product Details:
   - Assigned Identification: 002
   - Quantity Invoiced: 96 cases
   - Unit Price: $17.94
   - Product/service ID (Buyer's Item Number): 009236477
   - Item Description: 8/48oz PSTA ELBOW MAC 08B - GRVAL
   - Pack: 8

2.⁠ ⁠Product Details:
   - Assigned Identification: 003
   - Quantity Invoiced: 216 cases
   - Unit Price: $8.65
   - Product/service ID (Buyer's Item Number): 009265629
   - Item Description: 12/12oz PSTA BOWTIE 38B - GRVAL
   - Pack: 12

3.⁠ ⁠Product Details:
   - Assigned Identification: 004
   - Quantity Invoiced: 360 cases
   - Unit Price: $9.71
   - Product/service ID (Buyer's Item Number): 009265637
   
Please note that other details such as size, packaging code, weight, gross weight per pack, gross volume per pack, length, width, height, inner pack, and other identifiers are not available.The following information provides a detailed overview of specific products:

1.⁠ ⁠The first product, identified by the buyer's item number 009267031, has an assigned identification of 005. It has been described as '12/16oz PSTA PENNE RIG 310B - GRVAL'. The product is packed in the unit measurement of cases with a quantity of 120 invoiced at a unit price of $10.87.

2.⁠ ⁠The second product, identified by the buyer's item number 009278957, has an assigned identification of 006. Its description is '12/16oz PSTA ROTINI GRDN50/25/25 - GRVAL'. This item is also packed by cases, with 160 units invoiced at a unit price of $16.55.

3.⁠ ⁠The third product, identified by the buyer's item number 009289199, has an assigned identification of 007. It is described as '12/16oz PSTA EGG NDL WDE 13G - GRVAL'. This item is packed in cases, with 64 units invoiced at a unit price of $16.66.

For all three products, the pack size is 12. However, the weight, volume, length, width, height, and inner pack details are not available. Similarly, the product/service IDs, agency code, and other qualifiers are not provided.Here is the information related to the products in a more structured and readable format:

Product 1:
•⁠  ⁠Description: 12/16oz PSTA EGG NDL MED 14G - GRVAL
•⁠  ⁠Pack: 12
•⁠  ⁠Assigned Identification: 008
•⁠  ⁠Quantity Invoiced: 104
•⁠  ⁠Unit Or Basis For Measurement: CASE
•⁠  ⁠Unit Price: 26.89
•⁠  ⁠Buyer's Item Number (Product/Service ID): 009289280

Product 2:
•⁠  ⁠Description: 8/4lb PSTA SPAG 03B - GRVAL
•⁠  ⁠Pack: 8
•⁠  ⁠Assigned Identification: 009
•⁠  ⁠Quantity Invoiced: 91
•⁠  ⁠Unit Or Basis For Measurement: CASE
•⁠  ⁠Unit Price: 13.8
•⁠  ⁠Buyer's Item Number (Product/Service ID): 551574685

Product 3:
•⁠  ⁠Description: 16/16oz PSTA SPAG 03B - GRVAL
•⁠  ⁠Pack: 16
(Note: The provided text ended abruptly without providing further information about the third product.)The information is related to the details of three different products. Here is the clear presentation of the same:

1.⁠ ⁠Product Details:
   - Assigned Identification: 010
   - Invoiced Quantity: 90 cases
   - Unit Price: $9.66
   - Product/Service Id (Buyer's Item Number): 652487407
   - Product Description: 12/16 PSTA SHELL SM 10B-GRVAL
   - Package Details: Pack of 12

2.⁠ ⁠Product Details:
   - Assigned Identification: 011
   - Invoiced Quantity: 144 cases
   - Unit Price: $17.8
   - Product/Service Id (Buyer's Item Number): 662661988
   - Product Description: 12/8 PSTA MANICOTTI-GRVAL
   - Package Details: Pack of 12

3.⁠ ⁠Product Details:
   - Assigned Identification: 012
   - Invoiced Quantity: 160 cases
   - Unit Price: $16.63
   - Product/Service Id (Buyer's Item Number): 666636767

Note that there are no available details for size, packaging code, weight, gross weight per pack, gross volume per pack, length, width, height, inner pack, surface/layer/position code, and assigned identification number. Also, the product/service id qualifier for all products is not provided.Here's the text in a more presentable format:

•⁠  ⁠Product details: The item described is a 12 pack of 16oz Pasta Egg Noodles with a 5.5% Gravy-Graval content. There are no specific characteristics, agency qualifiers, product description codes, or surface/layer/position codes associated with this product. All other product identifiers are not applicable.

•⁠  ⁠Packaging and Dimensions: The product comes in a pack of 12. There are no specifics available regarding the size, weight, volume, length, width, and height of the pack. The basis of measurement for these dimensions is also not provided. Furthermore, there's no information about the inner pack or an assigned identification number for the product.

•⁠  ⁠Cost: The total cost for this product is $28,935.24. No other amounts are specified.

•⁠  ⁠Shipping: The product is shipped via a private carrier. The order is ready for pickup but no specifics are available regarding the equipment used for shipping or the standard carrier alpha code. There's no reference identification, service level code, or status code for the shipment or order.

•⁠  ⁠Quantity and Units: A total of 1,995 units were shipped, with each unit being a case. The total weight of the shipment is 29,319 pounds. No information about the volume or quantity of each unit is provided.

•⁠  ⁠Transaction Details: This transaction includes 12 line items. No details regarding the weight, volume, and description of these items are provided. The hash total for the transaction is 1,995.

•⁠  ⁠Summary: The transaction concludes with a total of 53 included segments. The transaction set control number is 7540.
"""
# edis = asyncio.run(edi_converter.convert_text_to_edi("6303207447", "a7b1d279-0f35-4ab5-9e78-498be7b1de46"))

# print(edis)
# for edi in edis:
#    print(edi)

is_relevent = asyncio.run(edi_converter.is_segment_relevant("LX", "Product Details", text, ""))
print(is_relevent)
